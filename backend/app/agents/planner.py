import logging
import time
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.services.llm import generate_groq_json, LLMError
from app.models import DailyPlan, AgentLog, Setting
from app.database import SessionLocal
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

class ContentPlanItem(BaseModel):
    kind: str = Field(..., description="'post' or 'story'")
    property_id: int
    theme: str
    platform: str
    language: str
    scheduled_at: str

class ContentPlan(BaseModel):
    items: List[ContentPlanItem]

def fallback_deterministic_planner(date_str: str, properties: List[Dict], settings_dict: Dict) -> ContentPlan:
    """Fallback planner if LLM fails."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    is_weekend_prep = dt.weekday() in [3, 4] # Thu, Fri
    
    post_slots = settings_dict.get("post_slots", ["09:00", "15:00", "19:00"])
    story_slots = settings_dict.get("story_slots", ["11:00", "17:00", "20:00"])
    langs = settings_dict.get("languages", ["he", "en"])
    platforms = settings_dict.get("platforms_enabled", ["instagram"])
    
    # Adjust for Friday (avoid late)
    if dt.weekday() == 4:
        post_slots = [s for s in post_slots if int(s.split(":")[0]) < 16]
        if not post_slots: post_slots = ["08:00", "10:00", "12:00"]
        story_slots = [s for s in story_slots if int(s.split(":")[0]) < 16]
        if not story_slots: story_slots = ["09:00", "11:00", "13:00"]
        
    items = []
    prop_count = len(properties)
    themes = ["property_highlight", "amenities", "nature", "relaxation", "family", "romantic_getaway", "weekend_getaway", "booking_cta"]
    
    for i in range(3):
        # Posts
        p = properties[i % prop_count] if prop_count > 0 else {"id": 1}
        items.append(ContentPlanItem(
            kind="post",
            property_id=p["id"],
            theme="weekend_getaway" if is_weekend_prep else themes[i % len(themes)],
            platform=platforms[i % len(platforms)],
            language=langs[i % len(langs)],
            scheduled_at=f"{date_str}T{post_slots[i % len(post_slots)]}:00+03:00"
        ))
        
        # Stories
        p_s = properties[(i+1) % prop_count] if prop_count > 0 else {"id": 1}
        items.append(ContentPlanItem(
            kind="story",
            property_id=p_s["id"],
            theme="weekend_getaway" if is_weekend_prep else themes[(i+1) % len(themes)],
            platform=platforms[(i+1) % len(platforms)],
            language=langs[(i+1) % len(langs)],
            scheduled_at=f"{date_str}T{story_slots[i % len(story_slots)]}:00+03:00"
        ))
        
    return ContentPlan(items=items)

def planner_node(state: AgentState) -> AgentState:
    run_id = state.get("run_id") or str(uuid.uuid4())
    date_str = state["date"]
    
    db = SessionLocal()
    start_time = time.time()
    provider = "groq"
    plan_output = None
    status = "success"
    message = "Plan generated successfully"
    
    try:
        settings_db = db.query(Setting).all()
        settings_dict = {s.key: s.value for s in settings_db}
        
        properties = state.get("properties", [])
        recent_content = state.get("recent_content", [])
        
        sys_prompt = f"""You are a Social Media Content Planner for a vacation rental business in Israel.
Your output MUST be a JSON object matching this schema:
{{
  "items": [
    {{
      "kind": "post" or "story",
      "property_id": integer,
      "theme": string,
      "platform": string,
      "language": string,
      "scheduled_at": "YYYY-MM-DDTHH:MM:SS+03:00"
    }}
  ]
}}

Generate exactly 3 posts and 3 stories.
Rules:
- Valid themes: property_highlight, amenities, nature, relaxation, family, romantic_getaway, weekend_getaway, booking_cta.
- Vary the themes. On Thursday and Friday, prefer 'weekend_getaway'.
- Don't reuse a property within 3 days if enough properties exist. Use ONLY provided property IDs.
- Timezone is Asia/Jerusalem. Fri/Sat is weekend in Israel. Schedule Friday items early (before 16:00). Avoid late-Friday and Saturday-evening slots.
- Allowed platforms: {settings_dict.get('platforms_enabled')}
- Allowed languages: {settings_dict.get('languages')}
- Allowed post slots: {settings_dict.get('post_slots')}
- Allowed story slots: {settings_dict.get('story_slots')}
"""
        prompt = f"Plan for date: {date_str}\nProperties: {properties}\nRecent Content: {recent_content}"
        
        try:
            plan = generate_groq_json(prompt, sys_prompt, ContentPlan)
            plan_output = plan.model_dump()
        except LLMError as e:
            logger.warning(f"LLM Planner failed, using fallback: {e}")
            plan = fallback_deterministic_planner(date_str, properties, settings_dict)
            plan_output = plan.model_dump()
            provider = "deterministic_fallback"
            message = str(e)
            status = "fallback"
            
        existing_plan = db.query(DailyPlan).filter(DailyPlan.date == date_str).first()
        if existing_plan:
            existing_plan.plan = plan_output
        else:
            db.add(DailyPlan(date=date_str, plan=plan_output))
            
        duration_ms = int((time.time() - start_time) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="planner",
            status=status,
            provider=provider,
            duration_ms=duration_ms,
            message=message
        ))
        db.commit()
        
        state["plan"] = plan_output
        
    except Exception as e:
        db.rollback()
        logger.error(f"Planner node error: {e}")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(str(e))
        
        duration_ms = int((time.time() - start_time) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="planner",
            status="error",
            provider="system",
            duration_ms=duration_ms,
            message=str(e)
        ))
        db.commit()
    finally:
        db.close()
        
    return state
