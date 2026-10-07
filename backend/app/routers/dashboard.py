from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AutomationLog, ContentItem, GeneratedMedia, Property
from app.services.events import PROMOTABLE_TYPES, get_mode

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _agg(db: Session, model, **conditions):
    """One query returning several COUNTs: conditions = {name: sqlalchemy boolean expr}."""
    cols = [func.coalesce(func.sum(case((expr, 1), else_=0)), 0).label(name) for name, expr in conditions.items()]
    row = db.query(*cols).select_from(model).one()
    return {name: int(getattr(row, name) or 0) for name in conditions}


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Real counts straight from the database (3 aggregate queries + the mode setting)."""
    promotable = Property.type.in_(PROMOTABLE_TYPES)
    props = _agg(
        db, Property,
        total=promotable,
        pending=and_(promotable, Property.approval_status == "PENDING"),
        approved=and_(promotable, Property.approval_status == "APPROVED"),
        rejected=and_(promotable, Property.approval_status == "REJECTED"),
        failed_gen=Property.content_generation_status == "FAILED",
    )
    content = _agg(
        db, ContentItem,
        posts=ContentItem.kind == "post",
        stories=ContentItem.kind == "story",
        pending=ContentItem.approval_status == "PENDING",
        approved=ContentItem.approval_status == "APPROVED",
        scheduled=ContentItem.publish_status == "SCHEDULED",
        published=ContentItem.publish_status == "PUBLISHED",
        rejected=ContentItem.approval_status == "REJECTED",
        publish_failed=ContentItem.publish_status == "FAILED",
    )
    media = _agg(
        db, GeneratedMedia,
        images=and_(GeneratedMedia.media_type == "IMAGE", GeneratedMedia.is_ai_generated.is_(True),
                    GeneratedMedia.generation_status == "COMPLETED"),
        videos=and_(GeneratedMedia.media_type == "VIDEO", GeneratedMedia.generation_status == "COMPLETED"),
        failed=GeneratedMedia.generation_status == "FAILED",
    )
    mode = get_mode(db)
    return {
        "total_scraped": props["total"],
        "scraped_properties": props["total"],
        "pending_properties": props["pending"],
        "approved_properties": props["approved"],
        "rejected_properties": props["rejected"],
        "posts_generated": content["posts"],
        "stories_generated": content["stories"],
        "pending_content": content["pending"],
        "content_pending_review": content["pending"],
        "approved_content": content["approved"],
        "scheduled": content["scheduled"],
        "published": content["published"],
        "rejected_content": content["rejected"],
        "failed": content["publish_failed"],
        "images_generated": media["images"],
        "videos_generated": media["videos"],
        "failed_generations": media["failed"] + props["failed_gen"],
        "current_mode": mode,
        "approval_mode": mode,
        "posts_today": content["posts"],
        "stories_today": content["stories"],
        "pending_approval": content["pending"],
    }
