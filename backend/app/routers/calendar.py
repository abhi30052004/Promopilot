from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, defer

from app.config import get_settings
from app.database import get_db
from app.models import ContentItem, GeneratedMedia, Property, PublishLog

router = APIRouter(prefix="/calendar", tags=["Calendar"])
settings = get_settings()


def _parse_boundary(value: Optional[str], *, end: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        if len(value) == 10:
            suffix = "T23:59:59.999999" if end else "T00:00:00"
            local = datetime.fromisoformat(f"{value}{suffix}").replace(tzinfo=ZoneInfo(settings.TIMEZONE))
            return local.astimezone(timezone.utc).replace(tzinfo=None)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise HTTPException(422, "start and end must be ISO dates or datetimes") from exc


@router.get("")
def get_calendar(
    start: Optional[str] = None,
    end: Optional[str] = None,
    platform: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Calendar events = one per (content, platform) publish record that has a date."""
    start_at = _parse_boundary(start)
    end_at = _parse_boundary(end, end=True)
    if start_at and end_at and start_at > end_at:
        raise HTTPException(422, "start must be before end")

    # Event time = scheduled_at for scheduled items, published_at for published ones.
    query = db.query(PublishLog, ContentItem).options(defer(ContentItem.source_snapshot)).join(ContentItem, PublishLog.content_id == ContentItem.id)
    query = query.filter(PublishLog.status.in_(["SCHEDULED", "PUBLISHED"]), ContentItem.approval_status == "APPROVED")
    if platform:
        query = query.filter(PublishLog.platform == platform.lower())
    pairs = query.all()

    media_ids = {item.media_id for _l, item in pairs if item.media_id}
    prop_ids = {item.property_id for _l, item in pairs if item.property_id}
    media = {m.id: m for m in db.query(GeneratedMedia).filter(GeneratedMedia.id.in_(media_ids)).all()} if media_ids else {}
    props = {p.id: p for p in db.query(Property.id, Property.name, Property.source_url, Property.url).filter(Property.id.in_(prop_ids)).all()} if prop_ids else {}

    events = []
    for log, item in pairs:
        when = log.scheduled_at or log.published_at
        if not when:
            continue
        if start_at and when < start_at:
            continue
        if end_at and when > end_at:
            continue
        m = media.get(item.media_id)
        prop = props.get(item.property_id)
        events.append({
            "id": log.id,
            "publish_log_id": log.id,
            "content_id": item.id,
            "kind": item.kind,
            "language": item.language,
            "title": item.title,
            "caption": item.caption,
            "cta": item.cta,
            "platform": log.platform,
            "status": (log.status or "").upper(),
            "is_demo": bool(log.is_demo),
            "scheduled_at": log.scheduled_at,
            "published_at": log.published_at,
            "event_at": when,
            "property_id": item.property_id,
            "property_name": prop.name if prop else None,
            "media_url": m.storage_url if m else None,
            "media_type": m.media_type if m else None,
            "media_generation_status": m.generation_status if m else "PENDING",
            "is_ai_generated": bool(m and m.is_ai_generated),
        })
    events.sort(key=lambda e: e["event_at"])
    return events
