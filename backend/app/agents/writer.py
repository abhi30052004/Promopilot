import logging
import time
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.services.llm import generate_openai_json, LLMError
from app.services.rag import get_property_context
from app.services.vectorstore import index_content
from app.models import ContentItem, Setting, AgentLog
from app.database import SessionLocal
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

class WriterContent(BaseModel):
    caption: str = Field(..., description="The main text of the post/story")
    hashtags: str = Field(..., description="Space separated hashtags, e.g., '#vacation #israel'")
    cta: str = Field(..., description="Call to action text")
    link: str = Field(..., description="The URL to include")

def _write_single_item(db, item_info: dict, brand_tone: str, context: dict, feedback: str = None) -> WriterContent:
    platform = item_info["platform"]
    kind = item_info["kind"]
    lang = item_info["language"]
    theme = item_info["theme"]
    
    platform_rules = ""
    if kind == "story":
        platform_rules = "Keep it to 1-2 short lines suitable for a story overlay."
    elif platform == "instagram":
        platform_rules = "Make it emotional and visual. Include 8-12 hashtags."
    elif platform == "facebook":
        platform_rules = "Make it informative and medium length."
    elif platform == "tiktok":
        platform_rules = "Start with a short hook, followed by a concise caption."
    elif platform == "x":
        platform_rules = "CRITICAL: The entire output (caption + cta + link) MUST be under 280 characters in total."
    elif platform == "telegram":
        platform_rules = "Make it longer and informative, providing all useful details."
    
    lang_rule = "Write in natural Israeli Hebrew." if lang == "he" else "Write in natural English."
    
    sys_prompt = f"""You are a top-tier Social Media Copywriter for vacation rentals.
Brand Tone: {brand_tone}
Target Language: {lang_rule}
Theme: {theme}
Platform Rules: {platform_rules}

CRITICAL RULES:
- Use ONLY the verified facts provided below.
- NEVER invent prices, amenities, availability, discounts, addresses, or claims.
- If a fact is missing from the context, leave it out. Do not guess.
- ALWAYS include the property URL in the 'link' field.
- Your output must be a valid JSON matching the exact schema requested.
"""
    
    prompt = f"""Verified Property Facts:
Name: {context.get('name')}
Type: {context.get('type')}
Location: {context.get('location')}
Description: {context.get('description')}
Amenities: {context.get('amenities')}
URL: {context.get('url')}
"""
    if feedback:
        prompt += f"\nPREVIOUS ISSUES TO FIX:\n{feedback}\n\nPlease rewrite this {kind} for {platform} in {lang}, fixing all issues."
    else:
        prompt += f"\nPlease write a {kind} for {platform} in {lang}."
        
    return generate_openai_json(prompt, sys_prompt, WriterContent)

def writer_node(state: AgentState) -> AgentState:
    run_id = state.get("run_id") or str(uuid.uuid4())
    db = SessionLocal()
    start_time = time.time()
    
    try:
        settings_db = db.query(Setting).all()
        settings_dict = {s.key: s.value for s in settings_db}
        brand_tone = settings_dict.get("brand_tone", "relaxing")
        
        failed_results = [r for r in state.get("review_results", []) if not r.get("pass") and r.get("retry_count", 0) < 2]
        is_rewrite = len(failed_results) > 0
        
        drafts = state.get("drafts", []) if is_rewrite else []
        
        if is_rewrite:
            for r in failed_results:
                item = db.query(ContentItem).filter(ContentItem.id == r["id"]).first()
                if not item:
                    continue
                
                item.retry_count += 1
                context = get_property_context(item.property_id, db)
                item_info = {
                    "platform": item.platform,
                    "kind": item.kind,
                    "language": item.language,
                    "theme": item.theme
                }
                
                result = _write_single_item(db, item_info, brand_tone, context, item.review_notes)
                item.caption = result.caption
                item.hashtags = result.hashtags
                item.cta = result.cta
                item.link = context.get('url') or result.link
                item.status = "draft"
                db.commit()
                
                # update drafts list
                for d in drafts:
                    if d["id"] == item.id:
                        d["caption"] = item.caption
                        break
        else:
            plan_data = state.get("plan")
            if not plan_data or "items" not in plan_data:
                state.setdefault("errors", []).append("No plan available for writing")
                db.close()
                return state
                
            for item_plan in plan_data["items"]:
                property_id = item_plan["property_id"]
                context = get_property_context(property_id, db)
                if not context: continue
                
                result = _write_single_item(db, item_plan, brand_tone, context)
                
                try:
                    sch_at = datetime.fromisoformat(item_plan["scheduled_at"])
                except Exception:
                    sch_at = None
                    
                content_item = ContentItem(
                    property_id=property_id,
                    kind=item_plan["kind"],
                    theme=item_plan["theme"],
                    platform=item_plan["platform"],
                    language=item_plan["language"],
                    scheduled_at=sch_at,
                    caption=result.caption,
                    hashtags=result.hashtags,
                    cta=result.cta,
                    link=context.get('url') or result.link,
                    status="draft"
                )
                db.add(content_item)
                db.commit()
                db.refresh(content_item)
                
                index_content(content_item)
                
                drafts.append({
                    "id": content_item.id,
                    "kind": content_item.kind,
                    "platform": content_item.platform,
                    "language": content_item.language,
                    "caption": content_item.caption
                })
                
        state["drafts"] = drafts
        
        duration_ms = int((time.time() - start_time) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="writer",
            status="success",
            provider="openai",
            duration_ms=duration_ms,
            message=f"Generated/Rewrote {len(drafts)} drafts"
        ))
        db.commit()
        
    except Exception as e:
        logger.error(f"Writer node error: {e}")
        state.setdefault("errors", []).append(str(e))
    finally:
        db.close()
        
    return state
