from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import ContentItem, GeneratedMedia, Property


router = APIRouter(prefix="/calendar", tags=["Calendar"])
settings = get_settings()


def _parse_boundary(value: Optional[str], *, end: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        if len(value) == 10:
            suffix = "T23:59:59.999999" if end else "T00:00:00"
            local = datetime.fromisoformat(f"{value}{suffix}").replace(
                tzinfo=ZoneInfo(settings.TIMEZONE)
            )
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
    db: Session = Depends(get_db),
):
    """Return persisted scheduled/published content for the requested calendar window."""
    start_at = _parse_boundary(start)
    end_at = _parse_boundary(end, end=True)
    if start_at and end_at and start_at > end_at:
        raise HTTPException(422, "start must be before end")

    query = db.query(ContentItem).filter(
        ContentItem.publish_status.in_(["SCHEDULED", "PUBLISHED"]),
        ContentItem.scheduled_at.is_not(None),
    )
    if start_at:
        query = query.filter(ContentItem.scheduled_at >= start_at)
    if end_at:
        query = query.filter(ContentItem.scheduled_at <= end_at)

    items = query.order_by(ContentItem.scheduled_at.asc()).all()
    result = []
    for item in items:
        row = {column.name: getattr(item, column.name) for column in item.__table__.columns}
        prop = db.query(Property).filter(Property.id == item.property_id).first()
        media = (
            db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
            if item.media_id
            else None
        )
        row.update(
            property_name=prop.name if prop else None,
            media_url=media.storage_url if media else None,
            media_type=media.media_type if media else None,
            media_generation_status=media.generation_status if media else "PENDING",
            is_ai_generated=bool(media and media.is_ai_generated),
        )
        result.append(row)
    return result
