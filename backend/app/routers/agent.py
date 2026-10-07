from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel

from app.database import get_db
from app.models import ContentItem, Property, AgentLog
from app.agents.state import AgentState
from app.agents.graph import app_graph

router = APIRouter(prefix="/agent", tags=["Agent"])

class RunAgentRequest(BaseModel):
    date: str
    mode: str = "manual"

@router.post("/run")
def run_agent(req: RunAgentRequest, db: Session = Depends(get_db)):
    try:
        datetime.strptime(req.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date format, use YYYY-MM-DD")
        
    props = db.query(Property).all()
    properties_data = [{"id": p.id, "name": p.name, "type": p.type, "location": p.location} for p in props]
    
    end_date = datetime.strptime(req.date, "%Y-%m-%d")
    start_date = end_date - timedelta(days=7)
    recent_items = db.query(ContentItem).filter(
        ContentItem.created_at >= start_date,
        ContentItem.created_at < end_date
    ).all()
    
    recent_content = []
    for item in recent_items:
        recent_content.append({
            "id": item.id,
            "property_id": item.property_id,
            "theme": item.theme,
            "platform": item.platform,
            "scheduled_at": str(item.scheduled_at) if item.scheduled_at else None
        })
        
    run_id = str(uuid.uuid4())
    
    initial_state = AgentState(
        date=req.date,
        properties=properties_data,
        recent_content=recent_content,
        plan=None,
        drafts=[],
        creatives=[],
        review_results=[],
        mode=req.mode,
        run_id=run_id,
        errors=[]
    )
    
    final_state = app_graph.invoke(initial_state)
    
    if final_state.get("errors"):
        return {"status": "error", "run_id": run_id, "errors": final_state["errors"], "drafts": final_state.get("drafts")}
        
    return {"status": "ok", "run_id": run_id, "drafts": final_state.get("drafts")}

@router.get("/runs/{run_id}")
def get_agent_run(run_id: str, db: Session = Depends(get_db)):
    logs = db.query(AgentLog).filter(AgentLog.run_id == run_id).order_by(AgentLog.created_at.asc()).all()
    if not logs:
        raise HTTPException(404, "Run not found")
        
    return {
        "run_id": run_id,
        "logs": [
            {
                "agent": log.agent,
                "status": log.status,
                "provider": log.provider,
                "duration_ms": log.duration_ms,
                "message": log.message,
                "created_at": log.created_at
            }
            for log in logs
        ]
    }
