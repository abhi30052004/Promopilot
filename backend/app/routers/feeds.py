from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import ContentItem, GeneratedMedia, Property, PublishLog

router = APIRouter(prefix="/feeds", tags=["Feeds"])


def _enrich(item: ContentItem, db: Session) -> dict:
    d = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    if item.media_id:
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
        d["media_url"] = media.storage_url if media else None
        d["media_type"] = media.media_type if media else None
        d["is_ai_generated"] = media.is_ai_generated if media else False
        d["media_mime"] = media.mime_type if media else None
        d["media_generation_status"] = media.generation_status if media else "FAILED"
    else:
        d["media_url"] = None
        d["media_type"] = None
        d["is_ai_generated"] = False
        d["media_mime"] = None
        d["media_generation_status"] = "FAILED"

    # Attach most recent publish log
    log = (
        db.query(PublishLog)
        .filter(PublishLog.content_item_id == item.id)
        .order_by(PublishLog.created_at.desc())
        .first()
    )
    d["last_publish_log"] = {
        "status": log.status if log else None,
        "external_post_id": log.external_post_id if log else None,
        "published_at": log.published_at if log else None,
        "error": log.error if log else None,
    } if log else None
    d["external_id"] = log.external_post_id if log else None
    d["publish_error"] = log.error if log else item.error
    prop = db.query(Property).filter(Property.id == item.property_id).first()
    d["property_name"] = prop.name if prop else None

    return d


@router.get("")
def get_all_feeds(
    platform: Optional[str] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return Published, Scheduled and Failed items with media."""
    query = db.query(ContentItem).filter(
        ContentItem.publish_status.in_(["PUBLISHED", "SCHEDULED", "FAILED"])
    )
    if platform:
        query = query.filter(ContentItem.platform == platform)
    if kind:
        query = query.filter(ContentItem.kind == kind)

    items = query.order_by(ContentItem.published_at.desc(), ContentItem.scheduled_at.desc()).all()
    return [_enrich(i, db) for i in items]


@router.get("/{platform}")
def get_feed(
    platform: str,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ContentItem).filter(
        ContentItem.platform == platform,
        ContentItem.publish_status.in_(["PUBLISHED", "SCHEDULED", "FAILED"])
    )
    if kind:
        query = query.filter(ContentItem.kind == kind)

    items = query.order_by(ContentItem.published_at.desc(), ContentItem.scheduled_at.desc()).all()
    return [_enrich(i, db) for i in items]
