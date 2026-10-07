import re
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Setting
from app.services.events import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_PLATFORMS,
    get_contact_email,
    get_default_language,
    get_default_platforms,
    get_mode,
    log_event,
)

router = APIRouter(prefix="/settings", tags=["Settings"])

ALLOWED_SETTINGS = {
    "posts_per_day", "stories_per_day", "story_duration_seconds",
    "max_ai_images_per_property", "languages", "approval_mode",
    "platforms_enabled", "brand_tone", "post_slots", "story_slots",
    "default_language", "contact_email",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApprovalModeRequest(BaseModel):
    mode: str  # HUMAN | AUTOMATION


@router.get("")
def get_all_settings(db: Session = Depends(get_db)):
    """Persisted settings, with spec defaults filled in for anything not stored yet."""
    stored = {s.key: s.value for s in db.query(Setting).all()}
    stored["approval_mode"] = get_mode(db)
    stored["platforms_enabled"] = get_default_platforms(db)
    stored["default_language"] = get_default_language(db)
    stored["contact_email"] = get_contact_email(db)
    stored["story_duration_seconds"] = 10
    stored["supported_platforms"] = SUPPORTED_PLATFORMS
    stored["supported_languages"] = SUPPORTED_LANGUAGES
    stored["openai_configured"] = bool(get_settings().OPENAI_API_KEY)
    return stored


def _save(db: Session, key: str, value: Any) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


@router.put("")
def update_settings(updates: Dict[str, Any], db: Session = Depends(get_db)):
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
        value = updates["platforms_enabled"]
        if not isinstance(value, list) or not value or not set(value).issubset(SUPPORTED_PLATFORMS):
            raise HTTPException(422, "platforms_enabled must be a non-empty list of supported platforms")
    if "languages" in updates:
        if not isinstance(updates["languages"], list) or not set(updates["languages"]).issubset(SUPPORTED_LANGUAGES):
            raise HTTPException(422, "languages may contain only he and en")
    if "default_language" in updates and updates["default_language"] not in SUPPORTED_LANGUAGES:
        raise HTTPException(422, "default_language must be 'en' or 'he'")
    if "contact_email" in updates and not _EMAIL.match(str(updates["contact_email"]).strip()):
        raise HTTPException(422, "contact_email must be a valid e-mail address")

    previous_mode = get_mode(db)
    for key, value in updates.items():
        _save(db, key, value.strip() if key == "contact_email" else value)
    db.commit()
    if "approval_mode" in updates and updates["approval_mode"] != previous_mode:
        log_event(db, "MODE_CHANGED", "settings", None, "SUCCESS", mode=updates["approval_mode"])
    return {"status": "ok"}


@router.put("/approval-mode")
def set_approval_mode(req: ApprovalModeRequest, db: Session = Depends(get_db)):
    """Set approval mode: HUMAN | AUTOMATION. Newly scraped items follow the mode from then on."""
    mode = req.mode.upper()
    if mode not in ("HUMAN", "AUTOMATION"):
        raise HTTPException(400, "mode must be HUMAN or AUTOMATION")
    previous = get_mode(db)
    _save(db, "approval_mode", mode)
    db.commit()
    if previous != mode:
        log_event(db, "MODE_CHANGED", "settings", None, "SUCCESS", mode=mode)
    return {"status": "ok", "approval_mode": mode}
