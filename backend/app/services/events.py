"""Central audit-event + settings helpers shared by every workflow step."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AutomationLog, Setting

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = ["instagram", "facebook", "linkedin", "tiktok", "x", "telegram"]
SUPPORTED_LANGUAGES = ["en", "he"]
_OLD_DEFAULT_PLATFORMS = ["facebook", "instagram", "tiktok", "x", "telegram"]


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row is not None and row.value is not None else default


def get_mode(db: Session) -> str:
    """HUMAN | AUTOMATION (persisted in the settings table)."""
    env_default = get_settings().DEFAULT_APPROVAL_MODE
    value = get_setting(db, "approval_mode", "AUTOMATION" if str(env_default).lower().startswith("auto") else "HUMAN")
    return "AUTOMATION" if str(value).upper() == "AUTOMATION" else "HUMAN"


def get_default_platforms(db: Session) -> list[str]:
    value = get_setting(db, "platforms_enabled", None)
    if not isinstance(value, list) or not value:
        value = get_settings().default_platforms
    return [p for p in value if p in SUPPORTED_PLATFORMS]


def get_default_language(db: Session) -> str:
    value = get_setting(db, "default_language", None) or get_settings().DEFAULT_LANGUAGE
    return value if value in SUPPORTED_LANGUAGES else "en"


def get_contact_email(db: Session) -> str:
    return get_setting(db, "contact_email", None) or get_settings().DEFAULT_CONTACT_EMAIL


def log_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    status: str = "SUCCESS",
    *,
    error: Optional[str] = None,
    language: Optional[str] = None,
    platform: Optional[str] = None,
    mode: Optional[str] = None,
    commit: bool = True,
) -> None:
    """Persist one audit event (timestamp, action, entity, status, mode, language, platform, error)."""
    try:
        db.add(
            AutomationLog(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                mode=mode or get_mode(db),
                status=status,
                error=(error[:2000] if error else None),
                language=language,
                platform=platform,
            )
        )
        if commit:
            db.commit()
    except Exception:  # an audit failure must never break the workflow
        logger.exception("could not write audit event %s", action)
        db.rollback()
