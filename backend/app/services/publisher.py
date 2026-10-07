from sqlalchemy.orm import Session
from app.models import ContentItem, PublishLog
from app.adapters import get_adapter

class PublisherService:
    @staticmethod
    def publish_item(item: ContentItem, db: Session) -> bool:
        if item.status != "scheduled":
            raise ValueError("Item must be scheduled to publish")
            
        adapter = get_adapter(item.platform)
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            res = adapter.publish(item)
            
            log = PublishLog(
                content_item_id=item.id,
                platform=item.platform,
                status=res["status"],
                response=res,
                error=res.get("error"),
                attempt=attempt
            )
            db.add(log)
            db.commit()
            
            if res["status"] == "success":
                item.status = "published"
                from sqlalchemy.sql import func
                item.published_at = func.now()
                # we don't have published_url column, we can keep it in logs
                db.commit()
                return True
                
        item.status = "failed"
        db.commit()
        return False
