import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz
import uuid

from app.database import SessionLocal
from app.models import ContentItem, Setting
from app.services.publisher import PublisherService
from app.agents.state import AgentState
from app.agents.graph import app_graph

logger = logging.getLogger(__name__)

scheduler: Optional[BackgroundScheduler] = None

def get_scheduler_status():
    if not scheduler:
        return {"running": False}
    return {
        "running": scheduler.running,
        "jobs": [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    }

def run_daily_plan_job():
    db = SessionLocal()
    try:
        settings_db = db.query(Setting).all()
        settings_dict = {s.key: s.value for s in settings_db}
        mode = settings_dict.get("approval_mode", "manual")
        
        from app.models import Property
        props = db.query(Property).all()
        properties_data = [{"id": p.id, "name": p.name, "type": p.type, "location": p.location} for p in props]
        
        tz = pytz.timezone("Asia/Jerusalem")
        now_date = datetime.now(tz).strftime("%Y-%m-%d")
        
        initial_state = AgentState(
            date=now_date,
            properties=properties_data,
            recent_content=[],
            plan=None,
            drafts=[],
            creatives=[],
            review_results=[],
            mode=mode,
            run_id=str(uuid.uuid4()),
            errors=[]
        )
        app_graph.invoke(initial_state)
    except Exception as e:
        logger.error(f"Error in daily_plan_job: {e}")
    finally:
        db.close()

def publish_due_items_job():
    db = SessionLocal()
    try:
        tz = pytz.timezone("Asia/Jerusalem")
        now = datetime.now(tz).replace(tzinfo=None)
        
        items = db.query(ContentItem).filter(
            ContentItem.status == "scheduled",
            ContentItem.scheduled_at <= now
        ).all()
        
        for item in items:
            item.status = "publishing"
            db.commit()
            
            try:
                PublisherService.publish_item(item, db)
            except Exception as ex:
                logger.error(f"Error publishing item {item.id}: {ex}")
                item.status = "failed"
                db.commit()
                
    except Exception as e:
        logger.error(f"Error in publish_due_items_job: {e}")
    finally:
        db.close()

def start_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        return
        
    tz = pytz.timezone("Asia/Jerusalem")
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
    
    scheduler.start()
    logger.info("Scheduler started.")

def stop_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
