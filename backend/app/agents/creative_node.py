import logging
import time
import uuid
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ContentItem, Property, AgentLog
from app.agents.state import AgentState
from app.services.creative import render_creative

logger = logging.getLogger(__name__)

def creative_node(state: AgentState) -> AgentState:
    run_id = state.get("run_id") or str(uuid.uuid4())
    db = SessionLocal()
    start_time = time.time()
    
    drafts = state.get("drafts", [])
    
    try:
        for draft in drafts:
            item_id = draft.get("id")
            if not item_id: continue
            
            item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
            if not item: continue
            
            prop = db.query(Property).filter(Property.id == item.property_id).first()
            
            try:
                rel_path = render_creative(item, prop)
                item.image_path = rel_path
                db.commit()
            except Exception as e:
                logger.error(f"Creative generation failed for item {item.id}: {e}")
                state.setdefault("errors", []).append(f"Creative error for item {item.id}: {e}")
                
        duration_ms = int((time.time() - start_time) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="creative",
            status="success",
            provider="pillow",
            duration_ms=duration_ms,
            message=f"Generated {len(drafts)} images"
        ))
        db.commit()
        
    except Exception as e:
        logger.error(f"Creative node error: {e}")
        state.setdefault("errors", []).append(str(e))
    finally:
        db.close()
        
    return state
