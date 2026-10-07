import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import ContentItem, DailyPlan, Property
from app.agents.state import AgentState
from app.agents.graph import app_graph
from app.services.translation import translate_item
from app.services.creative import render_creative
from app.agents.reviewer import run_review
from app.services.publisher import PublisherService
import urllib.parse
from app.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/content", tags=["Content"])

def validate_transition(current_status: str, new_status: str) -> bool:
    if current_status == "rejected" and new_status in ["scheduled", "published"]:
        return False
        
    allowed = {
        "draft": ["pending_approval", "failed"],
        "pending_approval": ["approved", "rejected", "draft"],
        "approved": ["scheduled", "pending_approval", "draft"],
        "scheduled": ["published", "failed", "pending_approval", "draft"],
        "rejected": ["draft", "pending_approval"],
        "failed": ["draft", "pending_approval"],
        "published": []
    }
    return new_status in allowed.get(current_status, [])

class GenerateContentRequest(BaseModel):
    date: str

class TranslateRequest(BaseModel):
    target_lang: str

@router.post("/generate")
def generate_content(req: GenerateContentRequest, db: Session = Depends(get_db)):
    plan = db.query(DailyPlan).filter(DailyPlan.date == req.date).first()
    if not plan:
        raise HTTPException(404, "Plan not found for date")
        
    run_id = str(uuid.uuid4())
    state = AgentState(
        date=req.date,
        properties=[],
        recent_content=[],
        plan=plan.plan,
        drafts=[],
        creatives=[],
        review_results=[],
        mode="write",
        run_id=run_id,
        errors=[]
    )
    
    final_state = app_graph.invoke(state)
    
    if final_state.get("errors"):
        return {"status": "error", "errors": final_state["errors"], "drafts": final_state.get("drafts")}
        
    return {"status": "ok", "drafts": final_state.get("drafts")}

@router.post("/{item_id}/translate")
def translate_content_item(item_id: int, req: TranslateRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
        
    try:
        translated_item = translate_item(item, req.target_lang)
        db.add(translated_item)
        db.commit()
        db.refresh(translated_item)
        
        return {
            "status": "ok",
            "original": {
                "id": item.id,
                "language": item.language,
                "caption": item.caption
            },
            "translated": {
                "id": translated_item.id,
                "language": translated_item.language,
                "caption": translated_item.caption
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Translation failed: {str(e)}")

@router.post("/{item_id}/creative")
def generate_creative(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
        
    prop = db.query(Property).filter(Property.id == item.property_id).first()
    
    try:
        rel_path = render_creative(item, prop)
        item.image_path = rel_path
        db.commit()
        
        base = settings.MEDIA_BASE_URL
        if not base.endswith('/'):
            base += '/'
            
        public_url = urllib.parse.urljoin(base, rel_path)
        return {"status": "ok", "url": public_url, "path": rel_path}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Creative generation failed: {str(e)}")

@router.post("/{item_id}/review")
def review_content_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
        
    try:
        res = run_review(item, db)
        item.review_score = res.score
        
        import json
        item.review_notes = json.dumps(res.issues, ensure_ascii=False)
        
        if res.pass_flag:
            item.status = "pending_approval"
        else:
            if item.retry_count >= 2:
                item.status = "failed"
            else:
                item.status = "draft"
                
        db.commit()
        
        return {
            "status": "ok",
            "pass": res.pass_flag,
            "score": res.score,
            "issues": res.issues,
            "new_status": item.status
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Review failed: {str(e)}")

@router.post("/{item_id}/approve")
def approve_content(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item: raise HTTPException(404)
    if not validate_transition(item.status, "approved"):
        raise HTTPException(409, f"Invalid transition from {item.status} to approved")
    item.status = "approved"
    db.commit()
    return {"status": "ok", "new_status": item.status}

@router.post("/{item_id}/reject")
def reject_content(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item: raise HTTPException(404)
    if not validate_transition(item.status, "rejected"):
        raise HTTPException(409, f"Invalid transition from {item.status} to rejected")
    item.status = "rejected"
    db.commit()
    return {"status": "ok", "new_status": item.status}

@router.post("/{item_id}/schedule")
def schedule_content(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item: raise HTTPException(404)
    if not validate_transition(item.status, "scheduled"):
        raise HTTPException(409, f"Invalid transition from {item.status} to scheduled")
    item.status = "scheduled"
    db.commit()
    return {"status": "ok", "new_status": item.status}

@router.post("/{item_id}/regenerate")
def regenerate_content(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item: raise HTTPException(404)
    if not validate_transition(item.status, "draft"):
        raise HTTPException(409, f"Invalid transition from {item.status} to draft (regenerate)")
        
    item.status = "draft"
    item.retry_count = 0
    db.commit()
    
    state = AgentState(
        date="regenerate",
        properties=[],
        recent_content=[],
        plan=None,
        drafts=[],
        creatives=[],
        review_results=[{"id": item.id, "pass": False, "retry_count": 0}],
        mode="regenerate",
        run_id=str(uuid.uuid4()),
        errors=[]
    )
    
    app_graph.invoke(state)
    db.refresh(item)
    return {"status": "ok", "new_status": item.status}

class ContentUpdate(BaseModel):
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    cta: Optional[str] = None
    scheduled_at: Optional[str] = None

@router.patch("/{item_id}")
def update_content(item_id: int, req: ContentUpdate, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item: raise HTTPException(404)
    
    if req.caption is not None: item.caption = req.caption
    if req.hashtags is not None: item.hashtags = req.hashtags
    if req.cta is not None: item.cta = req.cta
    if req.scheduled_at is not None:
        try:
            item.scheduled_at = datetime.fromisoformat(req.scheduled_at)
        except:
            pass
            
    if item.status in ["approved", "scheduled"]:
        if not validate_transition(item.status, "pending_approval"):
            raise HTTPException(409, f"Invalid transition from {item.status} to pending_approval")
        item.status = "pending_approval"
        
    db.commit()
    db.refresh(item)
    return item

@router.post("/{item_id}/publish-now")
def publish_now(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item: raise HTTPException(404)
    if not validate_transition(item.status, "published"):
        if item.status != "scheduled":
            raise HTTPException(409, "Item must be scheduled to publish-now")
            
    success = PublisherService.publish_item(item, db)
    return {"status": "ok", "success": success, "new_status": item.status}

@router.get("")
def get_content(
    date: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ContentItem)
    if date:
        try:
            query = query.filter(
                ContentItem.scheduled_at >= f"{date}T00:00:00",
                ContentItem.scheduled_at <= f"{date}T23:59:59"
            )
        except Exception:
            pass
    if status:
        query = query.filter(ContentItem.status == status)
    if platform:
        query = query.filter(ContentItem.platform == platform)
    if kind:
        query = query.filter(ContentItem.kind == kind)
        
    return query.order_by(ContentItem.created_at.desc()).all()

@router.get("/{item_id}")
def get_content_by_id(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
    return item
