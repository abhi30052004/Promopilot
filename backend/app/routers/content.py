import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import pytz
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, defer

from app.agents.graph import app_graph
from app.agents.reviewer import run_review
from app.agents.state import AgentState
from app.config import get_settings
from app.database import get_db
from app.models import ContentItem, DailyPlan, GeneratedMedia, Property, PublishLog
from app.services.creative import render_creative
from app.services.events import get_default_platforms, log_event
from app.services.publishing import (
    PublishError,
    approve_and_publish,
    approve_and_schedule,
    refresh_item_status,
    reject_item,
    retry_failed,
)
from app.services.translation import translate_item

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/content", tags=["Content"])


# ----------------------------------------------------------------------------- serialization
def _log_dict(log: PublishLog) -> dict:
    return {
        "id": log.id,
        "platform": log.platform,
        "status": (log.status or "").upper(),
        "scheduled_at": log.scheduled_at,
        "published_at": log.published_at,
        "external_post_id": log.external_post_id,
        "is_demo": bool(log.is_demo),
        "error": log.error,
        "attempt": log.attempt,
    }


def serialize_items(items: List[ContentItem], db: Session) -> List[dict]:
    """Content rows enriched with media, property name and per-platform publish logs (no N+1)."""
    if not items:
        return []
    media_ids = {i.media_id for i in items if i.media_id}
    prop_ids = {i.property_id for i in items if i.property_id}
    item_ids = [i.id for i in items]
    media = {m.id: m for m in db.query(GeneratedMedia).filter(GeneratedMedia.id.in_(media_ids)).all()} if media_ids else {}
    props = {p.id: p for p in db.query(Property.id, Property.name, Property.source_url, Property.url).filter(Property.id.in_(prop_ids)).all()} if prop_ids else {}
    logs: dict[int, list] = {}
    for log in db.query(PublishLog).filter(PublishLog.content_id.in_(item_ids)).all():
        logs.setdefault(log.content_id, []).append(_log_dict(log))

    out = []
    for item in items:
        unloaded = sa_inspect(item).unloaded
        d = {c.name: getattr(item, c.name) for c in item.__table__.columns if c.key not in unloaded}
        m = media.get(item.media_id)
        d["media_url"] = m.storage_url if m else None
        d["media_type"] = m.media_type if m else None
        d["media_mime"] = m.mime_type if m else None
        d["is_ai_generated"] = bool(m and m.is_ai_generated)
        d["media_generation_status"] = m.generation_status if m else ("PENDING" if not item.media_id else "FAILED")
        d["media_error"] = m.error if m else None
        d["duration_seconds"] = m.duration_seconds if m else None
        prop = props.get(item.property_id)
        d["property_name"] = prop.name if prop else None
        d["property_url"] = (prop.source_url or prop.url) if prop else None
        d["platform_targets"] = item.platform_targets or ([item.platform] if item.platform else [])
        d["publish_logs"] = sorted(logs.get(item.id, []), key=lambda x: x["platform"] or "")
        d["content_type"] = (item.kind or "").upper()
        out.append(d)
    return out


def _get_item(item_id: int, db: Session) -> ContentItem:
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
    return item


def _publish_response(item: ContentItem, logs: List[PublishLog], db: Session) -> dict:
    db.refresh(item)
    row = serialize_items([item], db)[0]
    return {
        "status": "ok",
        "content": row,
        "publish_logs": [_log_dict(l) for l in logs],
        "demo": any(l.is_demo for l in logs),
        "publish_status": item.publish_status,
        "approval_status": item.approval_status,
    }


# ----------------------------------------------------------------------------- request models
class PlatformRequest(BaseModel):
    platforms: Optional[List[str]] = None


class ScheduleRequest(BaseModel):
    scheduled_at: str  # ISO datetime; naive values are interpreted in the app timezone
    platforms: Optional[List[str]] = None
    platform: Optional[str] = None  # legacy single-platform clients


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class RetryRequest(BaseModel):
    platform: Optional[str] = None


class GenerateContentRequest(BaseModel):
    date: str


class TranslateRequest(BaseModel):
    target_lang: str


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[Any] = None
    cta: Optional[str] = None


# ----------------------------------------------------------------------------- listing
@router.get("")
def get_content(
    date: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    kind: Optional[str] = None,
    language: Optional[str] = None,
    property_id: Optional[int] = None,
    approval_status: Optional[str] = None,
    publish_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ContentItem).options(defer(ContentItem.source_snapshot))
    if date:
        query = query.filter(ContentItem.generation_date == date)
    if status:
        query = query.filter(ContentItem.status == status)
    if kind:
        query = query.filter(ContentItem.kind == kind.lower())
    if language:
        query = query.filter(ContentItem.language == language)
    if property_id:
        query = query.filter(ContentItem.property_id == property_id)
    if approval_status:
        query = query.filter(ContentItem.approval_status == approval_status.upper())
    if publish_status:
        query = query.filter(ContentItem.publish_status == publish_status.upper())
    items = query.order_by(ContentItem.created_at.desc(), ContentItem.id.desc()).all()
    rows = serialize_items(items, db)
    if platform:
        rows = [r for r in rows if platform in (r["platform_targets"] or [])]
    return rows


@router.get("/{item_id}")
def get_content_by_id(item_id: int, db: Session = Depends(get_db)):
    return serialize_items([_get_item(item_id, db)], db)[0]


# ----------------------------------------------------------------------------- workflow actions
@router.post("/{item_id}/approve")
def approve_content(item_id: int, db: Session = Depends(get_db)):
    """Approve only (no publishing). Use /publish or /schedule to also publish."""
    item = _get_item(item_id, db)
    if item.approval_status == "REJECTED":
        raise HTTPException(409, "Cannot approve a rejected item")
    item.approval_status = "APPROVED"
    if item.publish_status in (None, "DRAFT", "PENDING"):
        item.status = "approved"
    db.commit()
    log_event(db, "CONTENT_APPROVED", "content_item", item.id, language=item.language)
    return {"status": "ok", "approval_status": item.approval_status, "new_status": item.status}


@router.post("/{item_id}/reject")
def reject_content(item_id: int, req: RejectRequest = None, db: Session = Depends(get_db)):
    item = _get_item(item_id, db)
    try:
        reject_item(item, req.reason if req else None, db)
    except PublishError as exc:
        raise HTTPException(409, str(exc))
    return {"status": "ok", "approval_status": item.approval_status, "new_status": item.status}


@router.post("/{item_id}/publish")
def publish_content(item_id: int, req: PlatformRequest = None, db: Session = Depends(get_db)):
    """Approve & Post: approve, then publish to every selected platform (one PublishLog each)."""
    item = _get_item(item_id, db)
    platforms = (req.platforms if req and req.platforms else None) or item.platform_targets or get_default_platforms(db)
    try:
        logs = approve_and_publish(item, platforms, db)
    except PublishError as exc:
        raise HTTPException(409, str(exc))
    return _publish_response(item, logs, db)


def _parse_schedule_time(value: str) -> datetime:
    try:
        tz = pytz.timezone(settings.TIMEZONE)
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt.astimezone(pytz.utc).replace(tzinfo=None)
    except (TypeError, ValueError, pytz.UnknownTimeZoneError) as exc:
        raise HTTPException(422, "scheduled_at must be a valid ISO datetime") from exc


@router.post("/{item_id}/schedule")
def schedule_content(item_id: int, req: ScheduleRequest, db: Session = Depends(get_db)):
    """Approve & Schedule: approve, then create one SCHEDULED PublishLog per selected platform."""
    item = _get_item(item_id, db)
    when = _parse_schedule_time(req.scheduled_at)
    platforms = req.platforms or ([req.platform] if req.platform else None) or item.platform_targets or get_default_platforms(db)
    try:
        logs = approve_and_schedule(item, platforms, when, db)
    except PublishError as exc:
        raise HTTPException(409 if "future" not in str(exc) else 422, str(exc))
    return _publish_response(item, logs, db)


@router.post("/{item_id}/retry")
def retry_content(item_id: int, req: RetryRequest = None, db: Session = Depends(get_db)):
    """Retry failed platform publishes (all failed platforms, or just ``platform``)."""
    item = _get_item(item_id, db)
    try:
        logs = retry_failed(item, db, req.platform if req else None)
    except PublishError as exc:
        raise HTTPException(409, str(exc))
    return _publish_response(item, logs, db)


@router.post("/{item_id}/generate")
@router.post("/{item_id}/regenerate")
def regenerate_content(item_id: int, db: Session = Depends(get_db)):
    """(Re)generate the text and media of one existing, unpublished content item."""
    from app.services.content_generator import regenerate_item

    item = _get_item(item_id, db)
    try:
        regenerate_item(item, db)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Generation failed: {exc}")
    return {"status": "ok", "content": serialize_items([item], db)[0]}


@router.patch("/{item_id}")
def update_content(item_id: int, req: ContentUpdate, db: Session = Depends(get_db)):
    item = _get_item(item_id, db)
    if item.publish_status == "PUBLISHED":
        raise HTTPException(409, "Published content cannot be edited")
    for field in ("title", "caption", "hashtags", "cta"):
        value = getattr(req, field)
        if value is not None:
            setattr(item, field, value)
    # Editing approved/scheduled content sends it back to review
    if item.approval_status == "APPROVED":
        for log in db.query(PublishLog).filter(PublishLog.content_id == item.id).all():
            if (log.status or "").upper() in ("SCHEDULED", "FAILED"):
                db.delete(log)
        item.approval_status = "PENDING"
        item.publish_status = "DRAFT"
        item.status = "pending_approval"
        item.scheduled_at = None
    db.commit()
    return serialize_items([item], db)[0]


# ----------------------------------------------------------------------------- legacy helpers
@router.post("/generate")
def generate_content(req: GenerateContentRequest, db: Session = Depends(get_db)):
    """Legacy plan-based generation (LangGraph). Property based generation lives under /properties."""
    plan = db.query(DailyPlan).filter(DailyPlan.date == req.date).first()
    if not plan:
        raise HTTPException(404, "Plan not found for date")
    state = AgentState(
        date=req.date, properties=[], recent_content=[], plan=plan.plan, drafts=[], creatives=[],
        review_results=[], mode="write", run_id=str(uuid.uuid4()), errors=[],
    )
    final_state = app_graph.invoke(state)
    if final_state.get("errors"):
        return {"status": "error", "errors": final_state["errors"], "drafts": final_state.get("drafts")}
    return {"status": "ok", "drafts": final_state.get("drafts")}


@router.post("/{item_id}/translate")
def translate_content_item(item_id: int, req: TranslateRequest, db: Session = Depends(get_db)):
    item = _get_item(item_id, db)
    try:
        translated_item = translate_item(item, req.target_lang)
        db.add(translated_item)
        db.commit()
        db.refresh(translated_item)
        return {
            "status": "ok",
            "original": {"id": item.id, "language": item.language, "caption": item.caption},
            "translated": {"id": translated_item.id, "language": translated_item.language, "caption": translated_item.caption},
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Translation failed: {str(e)}")


@router.post("/{item_id}/creative")
def generate_creative(item_id: int, db: Session = Depends(get_db)):
    item = _get_item(item_id, db)
    prop = db.query(Property).filter(Property.id == item.property_id).first()
    try:
        rel_path = render_creative(item, prop)
        from app.services.media_storage import save_generated_media

        path = os.path.join(settings.MEDIA_DIR, rel_path)
        with open(path, "rb") as file_handle:
            media = save_generated_media(
                db, file_handle.read(), item.property_id, item.id, "IMAGE", "PILLOW", "image/jpeg", "jpg",
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
    item = _get_item(item_id, db)
    try:
        res = run_review(item, db)
        item.review_score = res.score
        item.review_notes = json.dumps(res.issues, ensure_ascii=False)
        if res.pass_flag:
            item.approval_status = "PENDING"
            item.status = "pending_approval"
        else:
            item.status = "failed" if item.retry_count >= 2 else "draft"
        db.commit()
        return {"status": "ok", "pass": res.pass_flag, "score": res.score, "issues": res.issues, "new_status": item.status}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Review failed: {str(e)}")
