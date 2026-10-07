from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict, total=False):
    date: str
    properties: List[Dict[str, Any]]
    recent_content: List[Dict[str, Any]]
    plan: Optional[Dict[str, Any]]
    drafts: List[Dict[str, Any]]
    creatives: List[Dict[str, Any]]
    review_results: List[Dict[str, Any]]
    mode: str
    run_id: str
    errors: List[str]
    next_step: Optional[str]
