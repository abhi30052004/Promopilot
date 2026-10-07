import logging
import time
import uuid
import json
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ContentItem, AgentLog
from app.services.llm import generate_groq_json
from app.services.rag import get_property_context
from app.services.vectorstore import find_similar_content
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

class ReviewResult(BaseModel):
    pass_flag: bool = Field(alias="pass")
    score: int = Field(..., ge=0, le=100)
    issues: List[str]

def run_review(item: ContentItem, db: Session) -> ReviewResult:
    issues = []
    
    # 1. Deterministic Checks
    if not item.link and not (item.caption and 'http' in item.caption):
        issues.append("Link is missing.")
        
    if not item.cta:
        issues.append("CTA is missing.")
        
    text_length = len(item.caption or "") + len(item.cta or "") + len(item.link or "")
    if item.platform == "x" and text_length > 280:
        issues.append(f"Content exceeds X character limit (280). Current: {text_length}")
    if item.kind == "story" and len((item.caption or "").split('\n')) > 3:
        issues.append("Story caption is too long (should be 1-2 short lines).")
        
    if item.platform == "instagram":
        hashtags = item.hashtags
        if isinstance(hashtags, str):
            count = len([h for h in hashtags.split() if h.startswith('#')])
        elif isinstance(hashtags, list):
            count = len(hashtags)
        else:
            count = 0
            
        if not (8 <= count <= 12):
            issues.append(f"Instagram requires 8-12 hashtags, found {count}.")
            
    # Duplicate check
    if item.caption:
        similar = find_similar_content(item.caption, threshold=0.9)
        similar = [s for s in similar if s['id'] != item.id]
        if similar:
            issues.append("Content is too similar to existing generated content (duplicate).")
            
    # 2. LLM Review (Groq)
    context = get_property_context(item.property_id, db)
    
    sys_prompt = f"""You are a strict QA Reviewer for social media content.
Your job is to check for grammar, brand tone, and most importantly, unsupported claims.
You are given the Verified Property Facts.
The generated content MUST NOT invent amenities, prices, discounts, or location details not present in the facts.
Return a JSON object: {{"pass": bool, "score": int, "issues": [list of strings]}}.
If you find any hallucinated facts, missing facts, or bad grammar, add to issues and set pass=false.
"""
    prompt = f"""Verified Facts:
{json.dumps(context, ensure_ascii=False)}

Generated Content:
Platform: {item.platform}
Caption: {item.caption}
CTA: {item.cta}
Hashtags: {item.hashtags}
"""

    try:
        llm_result = generate_groq_json(prompt, sys_prompt, ReviewResult)
        
        final_issues = issues + llm_result.issues
        final_pass = len(final_issues) == 0 and llm_result.pass_flag
        final_score = llm_result.score if len(issues) == 0 else min(llm_result.score, 70)
        
        return ReviewResult(**{"pass": final_pass, "score": final_score, "issues": final_issues})
    except Exception as e:
        logger.error(f"Review LLM error: {e}")
        issues.append(f"LLM Review failed: {str(e)}")
        return ReviewResult(**{"pass": False, "score": 0, "issues": issues})

def reviewer_node(state: AgentState) -> AgentState:
    run_id = state.get("run_id") or str(uuid.uuid4())
    db = SessionLocal()
    start_time = time.time()
    
    drafts = state.get("drafts", [])
    review_results = []
    
    try:
        for draft in drafts:
            item_id = draft.get("id")
            if not item_id: continue
            
            item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
            if not item: continue
            
            res = run_review(item, db)
            
            item.review_score = res.score
            item.review_notes = json.dumps(res.issues, ensure_ascii=False)
                
            db.commit()
            
            review_results.append({
                "id": item.id,
                "pass": res.pass_flag,
                "score": res.score,
                "issues": res.issues,
                "retry_count": item.retry_count
            })
            
        state["review_results"] = review_results
        
        duration_ms = int((time.time() - start_time) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="reviewer",
            status="success",
            provider="groq",
            duration_ms=duration_ms,
            message=f"Reviewed {len(drafts)} drafts"
        ))
        db.commit()
        
    except Exception as e:
        logger.error(f"Reviewer node error: {e}")
        state.setdefault("errors", []).append(str(e))
    finally:
        db.close()
        
    return state
