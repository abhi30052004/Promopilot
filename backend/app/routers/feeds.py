from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ContentItem

router = APIRouter(prefix="/feeds", tags=["Feeds"])

@router.get("/{platform}")
def get_feed(platform: str, db: Session = Depends(get_db)):
    items = db.query(ContentItem).filter(
        ContentItem.platform == platform,
        ContentItem.status == "published"
    ).order_by(ContentItem.published_at.desc()).all()
    
    return items
