from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Any
import logging

from app.database import get_db
from app.models import Property
from app.services.vectorstore import search_properties, index_property

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

@router.post("/reindex")
def reindex_all(db: Session = Depends(get_db)):
    """
    Reindex all properties into ChromaDB.
    """
    try:
        properties = db.query(Property).all()
        count = 0
        for p in properties:
            index_property(p)
            count += 1
        return {"status": "ok", "reindexed": count}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
def search(q: str = Query(..., min_length=1), top_k: int = 5):
    """
    Search for properties using semantic search.
    """
    try:
        results = search_properties(query=q, top_k=top_k)
        return {"status": "ok", "query": q, "results": results}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
