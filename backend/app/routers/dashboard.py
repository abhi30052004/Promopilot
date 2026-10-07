from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.database import get_db
from app.models import ContentItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    
    base_query = db.query(ContentItem).filter(ContentItem.created_at >= today_start, ContentItem.created_at <= today_end)
    
    posts_count = base_query.filter(ContentItem.kind == "post").count()
    stories_count = base_query.filter(ContentItem.kind == "story").count()
    
    scheduled = base_query.filter(ContentItem.status == "scheduled").count()
    published = base_query.filter(ContentItem.status == "published").count()
    pending = base_query.filter(ContentItem.status == "pending_approval").count()
    failed = base_query.filter(ContentItem.status == "failed").count()
    
    return {
        "posts_today": posts_count,
        "stories_today": stories_count,
        "scheduled": scheduled,
        "published": published,
        "pending_approval": pending,
        "failed": failed
    }
