from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentLog, AutomationLog, PublishLog

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("")
def get_logs(
    type: Optional[str] = None,
    action: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Audit events (default), plus optional agent / publish technical logs.

    Every event row exposes: timestamp, action, entity, entityId, status, mode, language,
    platform, error.
    """
    results = []

    if type in (None, "automation", "events"):
        query = db.query(AutomationLog)
        if action:
            query = query.filter(AutomationLog.action == action.upper())
        if platform:
            query = query.filter(AutomationLog.platform.ilike(f"%{platform.lower()}%"))
        for e in query.order_by(AutomationLog.created_at.desc(), AutomationLog.id.desc()).limit(limit).all():
            results.append({
                "id": f"automation_{e.id}",
                "type": "automation",
                "timestamp": e.created_at,
                "created_at": e.created_at,
                "action": e.action,
                "entity": e.entity_type,
                "entity_type": e.entity_type,
                "entityId": e.entity_id,
                "entity_id": e.entity_id,
                "status": e.status,
                "mode": e.mode,
                "language": e.language,
                "platform": e.platform,
                "error": e.error,
            })

    if type in ("agent",):
        for l in db.query(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit).all():
            results.append({
                "id": f"agent_{l.id}", "type": "agent", "timestamp": l.created_at, "created_at": l.created_at,
                "run_id": l.run_id, "action": l.agent, "agent": l.agent, "entity": "llm", "status": l.status,
                "provider": l.provider, "duration_ms": l.duration_ms, "message": l.message,
                "mode": None, "language": None, "platform": None, "error": None,
            })

    if type in ("publish",):
        for l in db.query(PublishLog).order_by(PublishLog.updated_at.desc()).limit(limit).all():
            results.append({
                "id": f"publish_{l.id}", "type": "publish", "timestamp": l.updated_at or l.created_at,
                "created_at": l.updated_at or l.created_at, "action": f"PUBLISH_{(l.status or '').upper()}",
                "entity": "content_item", "entityId": l.content_id, "entity_id": l.content_id,
                "status": l.status, "mode": None, "language": None, "platform": l.platform,
                "error": l.error, "demo": bool(l.is_demo),
            })

    results.sort(key=lambda x: x["timestamp"] or datetime.min, reverse=True)
    return results[:limit]
