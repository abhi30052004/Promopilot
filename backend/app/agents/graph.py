from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.planner import planner_node
from app.agents.writer import writer_node
from app.agents.reviewer import reviewer_node
from app.agents.creative_node import creative_node

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Property, ContentItem, AgentLog
import time
import uuid

def ingest_check_node(state: AgentState):
    db = SessionLocal()
    start_time = time.time()
    run_id = state.get("run_id") or str(uuid.uuid4())
    
    try:
        count = db.query(Property).count()
        if count == 0:
            msg = "No properties exist. Please sync the website first."
            state.setdefault("errors", []).append(msg)
            db.add(AgentLog(run_id=run_id, agent="ingest_check", status="error", provider="system", duration_ms=int((time.time()-start_time)*1000), message=msg))
            db.commit()
            return state
            
        db.add(AgentLog(run_id=run_id, agent="ingest_check", status="success", provider="system", duration_ms=int((time.time()-start_time)*1000), message="Properties exist."))
        db.commit()
    finally:
        db.close()
    return state

def router_node(state: AgentState):
    db = SessionLocal()
    start_time = time.time()
    run_id = state.get("run_id") or str(uuid.uuid4())
    mode = state.get("mode", "manual")
    
    next_step = "END"
    
    try:
        results = state.get("review_results", [])
        any_needs_rewrite = False
        
        for res in results:
            item = db.query(ContentItem).filter(ContentItem.id == res["id"]).first()
            if not item: continue
            
            if res.get("pass"):
                if mode == "auto":
                    item.status = "scheduled"
                else:
                    item.status = "pending_approval"
            else:
                if item.retry_count < 2:
                    any_needs_rewrite = True
                    item.status = "draft"
                else:
                    item.status = "pending_approval"
                    item.review_notes = (item.review_notes or "") + "\n[FLAGGED FOR HUMAN ATTENTION: Max retries exhausted]"
            db.commit()
            
        if any_needs_rewrite:
            next_step = "writer"
            
        db.add(AgentLog(run_id=run_id, agent="router", status="success", provider="system", duration_ms=int((time.time()-start_time)*1000), message=f"Routed to {next_step}"))
        db.commit()
    except Exception as e:
        state.setdefault("errors", []).append(str(e))
    finally:
        db.close()
        
    state["next_step"] = next_step
    return state

def build_graph():
    builder = StateGraph(AgentState)
    
    builder.add_node("ingest_check", ingest_check_node)
    builder.add_node("planner", planner_node)
    builder.add_node("writer", writer_node)
    builder.add_node("creative", creative_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("router", router_node)
    
    builder.set_entry_point("ingest_check")
    
    def route_after_ingest(state: AgentState):
        if state.get("errors"):
            return END
        if state.get("mode") == "regenerate":
            return "writer"
        return "planner"
        
    builder.add_conditional_edges("ingest_check", route_after_ingest, {"planner": "planner", END: END})
    builder.add_edge("planner", "writer")
    builder.add_edge("writer", "creative")
    builder.add_edge("creative", "reviewer")
    builder.add_edge("reviewer", "router")
    
    def route_after_router(state: AgentState):
        ns = state.get("next_step", "END")
        if ns == "writer":
            return "writer"
        return END
        
    builder.add_conditional_edges("router", route_after_router, {"writer": "writer", END: END})
    
    return builder.compile()

app_graph = build_graph()
