import threading
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from app.scheduler import run_daily_plan_job, get_scheduler_status, run_tick
from app.config import get_settings

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
public_router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

settings = get_settings()


@router.post("/run-daily")
def trigger_daily():
    t = threading.Thread(target=run_daily_plan_job, daemon=True)
    t.start()
    return {"status": "ok", "message": "Daily plan job triggered in background"}


@router.get("/status")
def status():
    return get_scheduler_status()


@public_router.post("/tick")
def external_tick(x_scheduler_token: Optional[str] = Header(None)):
    """
    External cron endpoint.  Protected by SCHEDULER_TOKEN header.
    Runs due-item publishing and (optionally) the daily plan.
    """
    token = settings.SCHEDULER_TOKEN
    if not token or x_scheduler_token != token:
        raise HTTPException(status_code=403, detail="Invalid scheduler token")

    t = threading.Thread(target=run_tick, daemon=True)
    t.start()
    return {"status": "ok", "message": "Tick triggered"}
