import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any, List, Optional

from app.database import get_db
from app.models import ContentItem, DailyPlan, Property, PublishLog, GeneratedMedia, AutomationLog
from app.agents.state import AgentState
from app.agents.graph import app_graph
from app.services.translation import translate_item
from app.services.creative import render_creative
from app.agents.reviewer import run_review
from app.services.publisher import PublisherService
import urllib.parse
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/content", tags=["Content"])


def _derived_status(item: ContentItem) -> str:
    """Derive legacy 'status' from approval_status + publish_status for backward compat."""
    if item.approval_status == "REJECTED":
        return "rejected"
    if item.publish_status == "PUBLISHED":
        return "published"
    if item.publish_status == "SCHEDULED":
        return "scheduled"
    if item.publish_status == "FAILED":
        return "failed"
    if item.approval_status == "APPROVED":
        return "approved"
    return "pending_approval" if item.status in ("pending_approval",) else (item.status or "draft")


def _sync_status(item: ContentItem):
    """Keep legacy 'status' field in sync with new fields."""
    item.status = _derived_status(item)


def _automation_log(db: Session, action: str, item_id: int, status: str = "SUCCESS", error: str = None):
    from app.models import Setting

    row = db.query(Setting).filter(Setting.key == "approval_mode").first()
    db.add(AutomationLog(
        action=action,
        entity_type="content_item",
        entity_id=item_id,
        mode=row.value if row else "HUMAN",
        status=status,
        error=error,
    ))


def _require_approved_property(item: ContentItem, db: Session) -> Property:
    prop = db.query(Property).filter(Property.id == item.property_id).first()
    if not prop or prop.approval_status != "APPROVED":
        raise HTTPException(409, "The linked property must be approved before content can be scheduled or published")
    return prop


class GenerateContentRequest(BaseModel):
    date: str


class TranslateRequest(BaseModel):
    target_lang: str


class ScheduleRequest(BaseModel):
    scheduled_at: str    # ISO datetime string
    platform: Optional[str] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None


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
            "original": {"id": item.id, "language": item.language, "caption": item.caption},
            "translated": {"id": translated_item.id, "language": translated_item.language, "caption": translated_item.caption}
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
        import os
        from app.services.media_storage import save_generated_media

        path = os.path.join(settings.MEDIA_DIR, rel_path)
        with open(path, "rb") as file_handle:
            media = save_generated_media(
                db,
                file_handle.read(),
                item.property_id,
                item.id,
                "IMAGE",
                "PILLOW",
                "image/jpeg",
                "jpg",
            )
        item.media_id = media.id
        item.image_path = media.storage_url
        db.commit()
        try:
            os.remove(path)
        except OSError:
            pass
        return {"status": "ok", "url": media.storage_url, "media_id": media.id}
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
            item.approval_status = "PENDING"
            item.status = "pending_approval"
        else:
            if item.retry_count >= 2:
                item.status = "failed"
            else:
                item.status = "draft"
        db.commit()
        return {"status": "ok", "pass": res.pass_flag, "score": res.score, "issues": res.issues, "new_status": item.status}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Review failed: {str(e)}")


@router.post("/{item_id}/approve")
def approve_content(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.approval_status == "REJECTED":
        raise HTTPException(409, "Cannot approve a rejected item")

    item.approval_status = "APPROVED"
    item.publish_status = item.publish_status or "DRAFT"
    _sync_status(item)
    _automation_log(db, "CONTENT_APPROVED", item.id)
    db.commit()
    return {"status": "ok", "approval_status": item.approval_status, "new_status": item.status}


@router.post("/{item_id}/reject")
def reject_content(item_id: int, req: RejectRequest = None, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.publish_status == "PUBLISHED":
        raise HTTPException(409, "Cannot reject an already published item")

    item.approval_status = "REJECTED"
    item.publish_status = "DRAFT"
    if req and req.reason:
        item.rejection_reason = req.reason
    _sync_status(item)
    _automation_log(db, "CONTENT_REJECTED", item.id)
    db.commit()
    return {"status": "ok", "approval_status": item.approval_status, "new_status": item.status}


@router.post("/{item_id}/publish")
def publish_content(item_id: int, db: Session = Depends(get_db)):
    """Approve & Post: approve + publish immediately."""
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.approval_status == "REJECTED":
        raise HTTPException(409, "Rejected items cannot be published")
    if item.publish_status == "PUBLISHED":
        return {"status": "ok", "publish_status": item.publish_status}
    _require_approved_property(item, db)
    media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
    if not media or media.generation_status != "COMPLETED" or not media.storage_url:
        raise HTTPException(409, "Media must be generated successfully before publishing")

    # Auto-approve
    item.approval_status = "APPROVED"
    item.publish_status = "SCHEDULED"  # needed by PublisherService
    item.status = "scheduled"
    db.commit()

    success = PublisherService.publish_item(item, db)
    db.refresh(item)
    return {"status": "ok", "success": success, "publish_status": item.publish_status, "new_status": item.status}


@router.post("/{item_id}/schedule")
def schedule_content(item_id: int, req: ScheduleRequest = None, db: Session = Depends(get_db)):
    """Approve & Schedule."""
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.approval_status == "REJECTED":
        raise HTTPException(409, "Rejected items cannot be scheduled")
    _require_approved_property(item, db)

    media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
    if not media or media.generation_status != "COMPLETED" or not media.storage_url:
        raise HTTPException(409, "Media must be generated successfully before scheduling")

    if not req or not req.scheduled_at:
        raise HTTPException(422, "scheduled_at is required")
    try:
        import pytz
        tz = pytz.timezone(settings.TIMEZONE)
        dt = datetime.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        scheduled_at = dt.astimezone(pytz.utc).replace(tzinfo=None)
    except (TypeError, ValueError, pytz.UnknownTimeZoneError) as exc:
        raise HTTPException(422, "scheduled_at must be a valid ISO datetime") from exc
    if scheduled_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(422, "scheduled_at must be in the future")

    item.approval_status = "APPROVED"
    item.publish_status = "SCHEDULED"
    item.scheduled_at = scheduled_at

    if req and req.platform:
        if req.platform not in {"facebook", "instagram", "tiktok", "x", "telegram"}:
            raise HTTPException(422, "Unsupported platform")
        item.platform = req.platform

    _sync_status(item)
    _automation_log(db, "CONTENT_APPROVED", item.id)
    _automation_log(db, "POST_SCHEDULED", item.id)
    db.add(PublishLog(
        content_item_id=item.id,
        content_id=item.id,
        platform=item.platform,
        status="scheduled",
        attempt=0,
    ))
    db.commit()
    return {"status": "ok", "publish_status": item.publish_status, "scheduled_at": item.scheduled_at, "new_status": item.status}


@router.post("/{item_id}/retry")
def retry_content(item_id: int, db: Session = Depends(get_db)):
    """Retry a FAILED publish."""
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.publish_status != "FAILED":
        raise HTTPException(409, "Only FAILED items can be retried")
    if item.approval_status == "REJECTED":
        raise HTTPException(409, "Rejected items cannot be published")
    _require_approved_property(item, db)

    item.publish_status = "SCHEDULED"
    item.status = "scheduled"
    db.commit()

    success = PublisherService.publish_item(item, db)
    db.refresh(item)
    return {"status": "ok", "success": success, "publish_status": item.publish_status}


@router.post("/{item_id}/regenerate")
def regenerate_content(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.publish_status == "PUBLISHED":
        raise HTTPException(409, "Cannot regenerate a published item")

    item.status = "draft"
    item.approval_status = "PENDING"
    item.publish_status = "DRAFT"
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
    hashtags: Optional[Any] = None
    cta: Optional[str] = None
    scheduled_at: Optional[str] = None


@router.patch("/{item_id}")
def update_content(item_id: int, req: ContentUpdate, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)

    if req.caption is not None:
        item.caption = req.caption
    if req.hashtags is not None:
        item.hashtags = req.hashtags
    if req.cta is not None:
        item.cta = req.cta
    if req.scheduled_at is not None:
        try:
            item.scheduled_at = datetime.fromisoformat(req.scheduled_at)
        except Exception:
            pass

    # Editing an approved/scheduled item bumps back to PENDING
    if item.approval_status == "APPROVED" and item.publish_status in ("DRAFT", "SCHEDULED"):
        item.approval_status = "PENDING"
        item.publish_status = "DRAFT"
        _sync_status(item)

    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/publish-now")
def publish_now(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404)
    if item.approval_status == "REJECTED":
        raise HTTPException(409, "Rejected items cannot be published")
    _require_approved_property(item, db)
    if item.publish_status not in ("SCHEDULED", "DRAFT"):
        if item.publish_status != "SCHEDULED":
            raise HTTPException(409, "Item must be scheduled to publish-now")

    item.publish_status = "SCHEDULED"
    item.status = "scheduled"
    db.commit()

    success = PublisherService.publish_item(item, db)
    return {"status": "ok", "success": success, "new_status": item.status}


@router.get("")
def get_content(
    date: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    kind: Optional[str] = None,
    approval_status: Optional[str] = None,
    publish_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ContentItem)
    if date:
        try:
            start = datetime.fromisoformat(f"{date}T00:00:00")
            end = datetime.fromisoformat(f"{date}T23:59:59.999999")
            query = query.filter(ContentItem.scheduled_at >= start, ContentItem.scheduled_at <= end)
        except ValueError:
            raise HTTPException(422, "date must use YYYY-MM-DD")
    if status:
        query = query.filter(ContentItem.status == status)
    if platform:
        query = query.filter(ContentItem.platform == platform)
    if kind:
        query = query.filter(ContentItem.kind == kind)
    if approval_status:
        query = query.filter(ContentItem.approval_status == approval_status)
    if publish_status:
        query = query.filter(ContentItem.publish_status == publish_status)

    items = query.order_by(ContentItem.created_at.desc()).all()

    # Enrich with media URL
    result = []
    for item in items:
        d = {c.name: getattr(item, c.name) for c in item.__table__.columns}
        if item.media_id:
            media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
            d["media_url"] = media.storage_url if media else None
            d["media_type"] = media.media_type if media else None
            d["is_ai_generated"] = media.is_ai_generated if media else False
            d["media_generation_status"] = media.generation_status if media else "FAILED"
        else:
            d["media_url"] = None
            d["media_type"] = None
            d["is_ai_generated"] = False
            d["media_generation_status"] = "PENDING"
        result.append(d)

    return result


@router.get("/{item_id}")
def get_content_by_id(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")

    d = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    if item.media_id:
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
        d["media_url"] = media.storage_url if media else None
        d["media_type"] = media.media_type if media else None
        d["is_ai_generated"] = media.is_ai_generated if media else False
        d["media_generation_status"] = media.generation_status if media else "FAILED"
    else:
        d["media_url"] = None
        d["media_type"] = None
        d["is_ai_generated"] = False
        d["media_generation_status"] = "PENDING"
    return d
