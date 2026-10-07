from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from app.config import get_settings
from app.services.llm import generate_openai_json, generate_groq_json, LLMError

router = APIRouter(prefix="/llm", tags=["LLM"])
settings = get_settings()

class TestResponse(BaseModel):
    message: str
    status: str

@router.get("/status")
def llm_status():
    """Returns configuration status of LLM providers."""
    return {
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY)
    }

class TestRequest(BaseModel):
    provider: str

@router.post("/test")
def llm_test(req: TestRequest):
    """Test a tiny JSON call per provider."""
    sys_prompt = "You are a helpful assistant. Ensure you reply in JSON matching the schema."
    prompt = "Say hello and set status to 'ok'"
    
    try:
        if req.provider.lower() == "openai":
            res = generate_openai_json(prompt, sys_prompt, TestResponse)
        elif req.provider.lower() == "groq":
            res = generate_groq_json(prompt, sys_prompt, TestResponse)
        else:
            raise HTTPException(status_code=400, detail="Invalid provider. Use 'openai' or 'groq'.")
            
        return res
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
