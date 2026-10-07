from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ContentItem, Property, Setting

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # Properties
    total_props = db.query(Property).count()
    pending_props = db.query(Property).filter(Property.approval_status == "PENDING").count()
    approved_props = db.query(Property).filter(Property.approval_status == "APPROVED").count()
    rejected_props = db.query(Property).filter(Property.approval_status == "REJECTED").count()

    # Content
    content_pending = db.query(ContentItem).filter(ContentItem.approval_status == "PENDING").count()
    content_approved = db.query(ContentItem).filter(ContentItem.approval_status == "APPROVED").count()
    content_scheduled = db.query(ContentItem).filter(ContentItem.publish_status == "SCHEDULED").count()
    content_published = db.query(ContentItem).filter(ContentItem.publish_status == "PUBLISHED").count()
    content_rejected = db.query(ContentItem).filter(ContentItem.approval_status == "REJECTED").count()
    content_failed = db.query(ContentItem).filter(ContentItem.publish_status == "FAILED").count()

    # Legacy compat fields
    posts_today = db.query(ContentItem).filter(ContentItem.kind == "post").count()
    stories_today = db.query(ContentItem).filter(ContentItem.kind == "story").count()
    mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()

    return {
        # Properties
        "scraped_properties": total_props,
        "pending_properties": pending_props,
        "approved_properties": approved_props,
        "rejected_properties": rejected_props,
        # Content
        "content_pending_review": content_pending,
        "approved_content": content_approved,
        "scheduled": content_scheduled,
        "published": content_published,
        "rejected_content": content_rejected,
        "failed": content_failed,
        # Legacy
        "posts_today": posts_today,
        "stories_today": stories_today,
        "pending_approval": content_pending,
        "approval_mode": mode_row.value if mode_row else "HUMAN",
    }
