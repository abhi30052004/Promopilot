import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz
import uuid

from app.database import SessionLocal
from app.models import ContentItem, Setting, Property, AutomationLog, PublishLog
from app.config import get_settings
from app.services.publishing import publish_due
from app.services.events import get_mode
from app.agents.state import AgentState
from app.agents.graph import app_graph

logger = logging.getLogger(__name__)

scheduler: Optional[BackgroundScheduler] = None
app_settings = get_settings()


def get_scheduler_status():
    if not scheduler:
        return {"running": False}
    return {
        "running": scheduler.running,
        "jobs": [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    }


def run_daily_plan_job():
    """
    Daily job (AUTOMATION mode only): pick one APPROVED property (least recently used) and
    generate 3 posts + 3 stories; automation then approves and schedules them.
    """
    db = SessionLocal()
    try:
        if get_mode(db) != "AUTOMATION":
            logger.info("Daily plan skipped: HUMAN approval mode")
            return
        tz = pytz.timezone(app_settings.TIMEZONE)
        now_date = datetime.now(tz).strftime("%Y-%m-%d")

        approved_props = db.query(Property).filter(Property.approval_status == "APPROVED").all()
        if not approved_props:
            logger.info("Daily plan: no APPROVED properties found")
            return

        def last_used(p):
            latest = db.query(ContentItem.generation_date).filter(ContentItem.property_id == p.id)                .order_by(ContentItem.generation_date.desc()).first()
            return latest[0] if latest else ""

        prop = sorted(approved_props, key=last_used)[0]
        from app.services.content_generator import generate_content_for_property
        result = generate_content_for_property(prop, db, generation_date=now_date)
        logger.info(f"Daily plan complete for {prop.name}: {result}")
    except Exception as e:
        logger.error(f"Error in daily_plan_job: {e}")
    finally:
        db.close()


def publish_due_items_job():
    """Publish every SCHEDULED PublishLog whose time has come (one log per platform)."""
    db = SessionLocal()
    try:
        publish_due(db)
    except Exception as e:
        logger.error(f"Error in publish_due_items_job: {e}")
    finally:
        db.close()


def recover_stuck_generating():
    """On startup, recover GeneratedMedia rows stuck in GENERATING state."""
    db = SessionLocal()
    try:
        from app.models import GeneratedMedia, PropertyImage
        stuck = db.query(GeneratedMedia).filter(GeneratedMedia.generation_status == "GENERATING").all()
        for m in stuck:
            logger.warning(f"Recovering stuck GENERATING media {m.id} → FAILED")
            m.generation_status = "FAILED"
            m.error = "Recovered from stuck GENERATING state on startup"
        if stuck:
            db.commit()
    except Exception as e:
        logger.error(f"Error recovering stuck jobs: {e}")
    finally:
        db.close()


def media_cleanup_job():
    """Enforce MEDIA_MAX_TOTAL_MB and clean up orphaned files."""
    db = SessionLocal()
    try:
        from app.config import get_settings
        from app.models import GeneratedMedia
        from app.services.media_storage import get_storage
        
        s = get_settings()
        if not s.MEDIA_MAX_TOTAL_MB:
            return
            
        max_bytes = s.MEDIA_MAX_TOTAL_MB * 1024 * 1024
        target_bytes = int(max_bytes * 0.9)
        storage = get_storage()
        
        # 1. Clean up GridFS orphans
        if s.STORAGE_BACKEND == "mongo":
            fs = storage.fs
            for file_doc in fs.find({}):
                media_id = file_doc.metadata.get("media_id") if file_doc.metadata else None
                file_id = str(file_doc._id)
                if not media_id:
                    logger.info(f"Cleanup: missing media_id in GridFS {file_id}, deleting")
                    storage.delete(file_id)
                    continue
                    
                media = db.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).first()
                if not media or media.storage_key != file_id:
                    logger.info(f"Cleanup: orphaned GridFS file {file_id} (media_id={media_id}), deleting")
                    storage.delete(file_id)
        
        # 2. Enforce capacity
        total_bytes_row = db.query(GeneratedMedia.size_bytes).filter(GeneratedMedia.size_bytes != None).all()
        used_bytes = sum([b[0] for b in total_bytes_row])
        
        if used_bytes > max_bytes:
            # Only delete truly unreferenced media. Never create a broken content or
            # property reference merely to meet a storage cap.
            content_media_ids = db.query(ContentItem.media_id).filter(ContentItem.media_id.is_not(None))
            property_media_ids = db.query(PropertyImage.media_id).filter(PropertyImage.media_id.is_not(None))
            rows_to_delete = db.query(GeneratedMedia).filter(
                ~GeneratedMedia.id.in_(content_media_ids),
                ~GeneratedMedia.id.in_(property_media_ids),
            ).order_by(GeneratedMedia.created_at.asc()).all()
            
            for row in rows_to_delete:
                if used_bytes <= target_bytes:
                    break
                
                size = row.size_bytes or 0
                if row.storage_key:
                    storage.delete(row.storage_key)
                    
                db.delete(row)
                db.commit()
                used_bytes -= size
                logger.info(f"Cleanup: deleted media {row.id} to free {size} bytes")
                
    except Exception as e:
        logger.error(f"Error in media_cleanup_job: {e}")
    finally:
        db.close()

def run_tick():
    """
    External-cron tick: publish due items + run daily plan if needed.
    Called by POST /api/scheduler/tick.
    """
    publish_due_items_job()


def start_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        return

    # Recover stuck jobs first
    try:
        recover_stuck_generating()
    except Exception as e:
        logger.error(f"Startup recovery error: {e}")

    tz = pytz.timezone(app_settings.TIMEZONE)
    scheduler = BackgroundScheduler(timezone=tz)

    scheduler.add_job(
        run_daily_plan_job,
        trigger=CronTrigger(hour=6, minute=0, timezone=tz),
        id="daily_plan_job",
        replace_existing=True
    )

    scheduler.add_job(
        publish_due_items_job,
        trigger=IntervalTrigger(minutes=1, timezone=tz),
        id="publish_due_items_job",
        replace_existing=True
    )

    scheduler.add_job(
        media_cleanup_job,
        trigger=IntervalTrigger(hours=1, timezone=tz),
        id="media_cleanup_job",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started.")


def stop_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
