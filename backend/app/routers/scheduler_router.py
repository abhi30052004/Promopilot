import threading
from fastapi import APIRouter, Depends
from app.scheduler import run_daily_plan_job, get_scheduler_status

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

@router.post("/run-daily")
def trigger_daily():
    t = threading.Thread(target=run_daily_plan_job)
    t.start()
    return {"status": "ok", "message": "Daily plan job triggered in background"}

@router.get("/status")
def status():
    return get_scheduler_status()
