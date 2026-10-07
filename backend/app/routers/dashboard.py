from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AutomationLog, ContentItem, GeneratedMedia, Property
from app.services.events import get_mode

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _count(db: Session, *filters, model=ContentItem) -> int:
    return db.query(func.count(model.id)).filter(*filters).scalar() or 0


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Real counts straight from the database (no cached or hard-coded numbers)."""
    total = _count(db, model=Property)
    pending_props = _count(db, Property.approval_status == "PENDING", model=Property)
    approved_props = _count(db, Property.approval_status == "APPROVED", model=Property)
    rejected_props = _count(db, Property.approval_status == "REJECTED", model=Property)

    posts = _count(db, ContentItem.kind == "post")
    stories = _count(db, ContentItem.kind == "story")
    pending = _count(db, ContentItem.approval_status == "PENDING")
    approved = _count(db, ContentItem.approval_status == "APPROVED")
    scheduled = _count(db, ContentItem.publish_status == "SCHEDULED")
    published = _count(db, ContentItem.publish_status == "PUBLISHED")
    rejected = _count(db, ContentItem.approval_status == "REJECTED")
    publish_failed = _count(db, ContentItem.publish_status == "FAILED")

    images = _count(
        db, GeneratedMedia.media_type == "IMAGE", GeneratedMedia.is_ai_generated.is_(True),
        GeneratedMedia.generation_status == "COMPLETED", model=GeneratedMedia,
    )
    videos = _count(
        db, GeneratedMedia.media_type == "VIDEO", GeneratedMedia.generation_status == "COMPLETED",
        model=GeneratedMedia,
    )
    failed_media = _count(db, GeneratedMedia.generation_status == "FAILED", model=GeneratedMedia)
    failed_props = _count(db, Property.content_generation_status == "FAILED", model=Property)
    failed_generations = failed_media + failed_props

    mode = get_mode(db)
    return {
        # Properties
        "total_scraped": total,
        "scraped_properties": total,
        "pending_properties": pending_props,
        "approved_properties": approved_props,
        "rejected_properties": rejected_props,
        # Generated content
        "posts_generated": posts,
        "stories_generated": stories,
        "pending_content": pending,
        "content_pending_review": pending,
        "approved_content": approved,
        "scheduled": scheduled,
        "published": published,
        "rejected_content": rejected,
        "failed": publish_failed,
        # Media
        "images_generated": images,
        "videos_generated": videos,
        "failed_generations": failed_generations,
        # Mode
        "current_mode": mode,
        "approval_mode": mode,
        # Legacy fields kept for older clients
        "posts_today": posts,
        "stories_today": stories,
        "pending_approval": pending,
    }
