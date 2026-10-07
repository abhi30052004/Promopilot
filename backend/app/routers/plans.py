from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel

from app.database import get_db
from app.models import DailyPlan, Property, ContentItem
from app.agents.state import AgentState
from app.agents.graph import app_graph

router = APIRouter(prefix="/plans", tags=["Plans"])

class GeneratePlanRequest(BaseModel):
    date: str # YYYY-MM-DD

@router.post("/generate")
def generate_plan(req: GeneratePlanRequest, db: Session = Depends(get_db)):
    try:
        datetime.strptime(req.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date format, use YYYY-MM-DD")
        
    props = db.query(Property).all()
    properties_data = [{"id": p.id, "name": p.name, "type": p.type, "location": p.location} for p in props]
    
    if not properties_data:
        raise HTTPException(400, "No properties found. Run sync first.")
        
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
        mode="generate",
        run_id=run_id,
        errors=[]
    )
    
    final_state = app_graph.invoke(initial_state)
    
    if final_state.get("errors"):
        return {"status": "error", "errors": final_state["errors"], "plan": final_state.get("plan")}
        
    return {"status": "ok", "run_id": run_id, "plan": final_state.get("plan")}

@router.get("/{date}")
def get_plan(date: str, db: Session = Depends(get_db)):
    plan = db.query(DailyPlan).filter(DailyPlan.date == date).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    return {"date": plan.date, "plan": plan.plan, "created_at": plan.created_at}
