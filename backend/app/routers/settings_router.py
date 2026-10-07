from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Property, Setting

router = APIRouter(prefix="/settings", tags=["Settings"])

ALLOWED_SETTINGS = {
    "posts_per_day", "stories_per_day", "story_duration_seconds",
    "max_ai_images_per_property", "languages", "approval_mode",
    "platforms_enabled", "brand_tone", "post_slots", "story_slots",
}


class ApprovalModeRequest(BaseModel):
    mode: str  # HUMAN | AUTOMATION


@router.get("")
def get_all_settings(db: Session = Depends(get_db)):
    settings_db = db.query(Setting).all()
    return {s.key: s.value for s in settings_db}


def _queue_existing_pending(bg: BackgroundTasks, db: Session) -> None:
    from app.routers.properties import _process_property_bg

    ids = [row[0] for row in db.query(Property.id).filter(Property.approval_status == "PENDING").all()]
    for property_id in ids:
        bg.add_task(_process_property_bg, property_id, True, True)


@router.put("")
def update_settings(updates: Dict[str, Any], bg: BackgroundTasks, db: Session = Depends(get_db)):
    unknown = set(updates) - ALLOWED_SETTINGS
    if unknown:
        raise HTTPException(400, f"Unknown settings: {', '.join(sorted(unknown))}")
    for field, minimum, maximum in (
        ("posts_per_day", 1, 10),
        ("stories_per_day", 0, 15),
        ("story_duration_seconds", 5, 30),
        ("max_ai_images_per_property", 0, 10),
    ):
        if field in updates:
            try:
                value = int(updates[field])
            except (TypeError, ValueError) as exc:
                raise HTTPException(422, f"{field} must be an integer") from exc
            if not minimum <= value <= maximum:
                raise HTTPException(422, f"{field} must be between {minimum} and {maximum}")
            updates[field] = value
    if "approval_mode" in updates:
        updates["approval_mode"] = str(updates["approval_mode"]).upper()
        if updates["approval_mode"] not in ("HUMAN", "AUTOMATION"):
            raise HTTPException(422, "approval_mode must be HUMAN or AUTOMATION")
    if "platforms_enabled" in updates:
        allowed_platforms = {"facebook", "instagram", "tiktok", "x", "telegram"}
        if not isinstance(updates["platforms_enabled"], list) or not set(updates["platforms_enabled"]).issubset(allowed_platforms):
            raise HTTPException(422, "platforms_enabled contains an unsupported platform")
    if "languages" in updates:
        if not isinstance(updates["languages"], list) or not set(updates["languages"]).issubset({"he", "en"}):
            raise HTTPException(422, "languages may contain only he and en")
    for k, v in updates.items():
        s = db.query(Setting).filter(Setting.key == k).first()
        if s:
            s.value = v
        else:
            s = Setting(key=k, value=v)
            db.add(s)
    db.commit()
    if updates.get("approval_mode") == "AUTOMATION":
        _queue_existing_pending(bg, db)
    return {"status": "ok"}


@router.put("/approval-mode")
def set_approval_mode(req: ApprovalModeRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Set approval mode: HUMAN | AUTOMATION"""
    mode = req.mode.upper()
    if mode not in ("HUMAN", "AUTOMATION"):
        raise HTTPException(400, "mode must be HUMAN or AUTOMATION")

    s = db.query(Setting).filter(Setting.key == "approval_mode").first()
    if s:
        s.value = mode
    else:
        s = Setting(key="approval_mode", value=mode)
        db.add(s)
    db.commit()
    if mode == "AUTOMATION":
        _queue_existing_pending(bg, db)
    return {"status": "ok", "approval_mode": mode}
