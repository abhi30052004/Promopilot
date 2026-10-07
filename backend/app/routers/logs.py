from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import AgentLog, PublishLog

router = APIRouter(prefix="/logs", tags=["Logs"])

@router.get("")
def get_logs(type: Optional[str] = None, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    results = []
    
    if type in [None, "agent"]:
        agent_logs = db.query(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit).all()
        for l in agent_logs:
            results.append({
                "id": f"agent_{l.id}",
                "type": "agent",
                "run_id": l.run_id,
                "agent": l.agent,
                "status": l.status,
                "provider": l.provider,
                "duration_ms": l.duration_ms,
                "retry_count": l.retry_count,
                "message": l.message,
                "created_at": l.created_at
            })
            
    if type in [None, "publish"]:
        publish_logs = db.query(PublishLog).order_by(PublishLog.created_at.desc()).limit(limit).all()
        for l in publish_logs:
            results.append({
                "id": f"publish_{l.id}",
                "type": "publish",
                "content_item_id": l.content_item_id,
                "platform": l.platform,
                "status": l.status,
                "response": l.response,
                "attempt": l.attempt,
                "error": l.error,
                "created_at": l.created_at
            })
            
    # Sort descending
    results.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
    
    return results[:limit]
