import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.models import AutomationLog, ContentItem, GeneratedMedia, Property, PublishLog, Setting
from app.adapters import get_adapter

logger = logging.getLogger(__name__)


class PublisherService:
    @staticmethod
    def publish_item(item: ContentItem, db: Session) -> bool:
        if item.publish_status not in ("SCHEDULED",) and item.status not in ("scheduled",):
            raise ValueError("Item must be scheduled to publish")
        if item.approval_status != "APPROVED":
            raise ValueError("Only approved content can be published")
        prop = db.query(Property).filter(Property.id == item.property_id).first()
        if not prop or prop.approval_status != "APPROVED":
            raise ValueError("The linked property must be approved before content can be published")
        if item.media_id is None:
            raise ValueError("Content cannot be published without media")
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
        if not media or media.generation_status != "COMPLETED" or not media.storage_url:
            raise ValueError("Content media is not ready")

        adapter = get_adapter(item.platform)
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                res = adapter.publish(item)
            except Exception as exc:
                res = {"status": "error", "error": str(exc)}

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            log = PublishLog(
                content_item_id=item.id,
                content_id=item.id,
                platform=item.platform,
                status=res["status"],
                response=res,
                error=res.get("error"),
                attempt=attempt,
                published_at=now if res["status"] == "success" else None,
                external_post_id=(
                    res.get("external_id") or res.get("post_id") or res.get("message_id")
                ),
            )
            db.add(log)
            db.commit()

            if res["status"] == "success":
                item.publish_status = "PUBLISHED"
                item.status = "published"
                item.published_at = now
                db.commit()
                mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
                db.add(AutomationLog(
                    action="POST_PUBLISHED",
                    entity_type="content_item",
                    entity_id=item.id,
                    mode=mode_row.value if mode_row else "HUMAN",
                    status="SUCCESS",
                ))
                db.commit()
                logger.info(f"Item {item.id} published on {item.platform}")
                return True

        # All attempts failed
        item.publish_status = "FAILED"
        item.status = "failed"
        mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
        db.add(AutomationLog(
            action="POST_FAILED",
            entity_type="content_item",
            entity_id=item.id,
            mode=mode_row.value if mode_row else "HUMAN",
            status="FAILED",
            error="Publishing failed after 3 attempts",
        ))
        db.commit()
        logger.error(f"Item {item.id} failed to publish after {max_attempts} attempts")
        return False
