from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContentItem, GeneratedMedia, Property, PublishLog

router = APIRouter(prefix="/feeds", tags=["Feeds"])

FEED_STATUSES = ("PUBLISHED", "SCHEDULED", "FAILED")


def _feed_rows(db: Session, platform: Optional[str], kind: Optional[str], status: Optional[str]) -> list[dict]:
    """One feed entry per PublishLog, so the same content shows up in every platform feed."""
    query = db.query(PublishLog, ContentItem).join(ContentItem, PublishLog.content_id == ContentItem.id)
    query = query.filter(PublishLog.status.in_(FEED_STATUSES), ContentItem.approval_status == "APPROVED")
    if platform and platform != "all":
        query = query.filter(PublishLog.platform == platform.lower())
    if status:
        query = query.filter(PublishLog.status == status.upper())
    if kind:
        query = query.filter(ContentItem.kind == kind.lower())
    pairs = query.all()
    if not pairs:
        return []

    media_ids = {item.media_id for _l, item in pairs if item.media_id}
    prop_ids = {item.property_id for _l, item in pairs if item.property_id}
    media = {m.id: m for m in db.query(GeneratedMedia).filter(GeneratedMedia.id.in_(media_ids)).all()} if media_ids else {}
    props = {p.id: p for p in db.query(Property).filter(Property.id.in_(prop_ids)).all()} if prop_ids else {}

    rows = []
    for log, item in pairs:
        m = media.get(item.media_id)
        prop = props.get(item.property_id)
        status_value = (log.status or "").upper()
        rows.append({
            "id": log.id,                      # publish log id (unique per content+platform)
            "publish_log_id": log.id,
            "content_id": item.id,
            "content_item_id": item.id,
            "platform": log.platform,
            "status": status_value,
            "publish_status": status_value,
            "is_demo": bool(log.is_demo),
            "label": ("DEMO PUBLISHED" if log.is_demo else "PUBLISHED") if status_value == "PUBLISHED" else status_value,
            "kind": item.kind,
            "language": item.language,
            "title": item.title,
            "caption": item.caption,
            "hashtags": item.hashtags,
            "cta": item.cta,
            "contact_email": item.contact_email,
            "link": item.link,
            "story_hook": item.story_hook,
            "story_message": item.story_message,
            "property_id": item.property_id,
            "property_name": prop.name if prop else None,
            "media_id": item.media_id,
            "media_url": m.storage_url if m else None,
            "media_type": m.media_type if m else None,
            "media_mime": m.mime_type if m else None,
            "media_generation_status": m.generation_status if m else "FAILED",
            "is_ai_generated": bool(m and m.is_ai_generated),
            "scheduled_at": log.scheduled_at,
            "published_at": log.published_at,
            "external_id": log.external_post_id,
            "external_post_id": log.external_post_id,
            "error": log.error,
            "publish_error": log.error,
            "attempt": log.attempt,
        })
    rows.sort(key=lambda r: str(r["published_at"] or r["scheduled_at"] or ""), reverse=True)
    return rows


@router.get("")
def get_all_feeds(
    platform: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Published, Scheduled and Failed publish records across all platforms."""
    return _feed_rows(db, platform, kind, status)


@router.get("/{platform}")
def get_feed(
    platform: str,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return _feed_rows(db, platform, kind, status)
