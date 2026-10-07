from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from ..database import get_db
from ..models import Property
from ..schemas import PropertyRead
from ..services.ingestion import sync_site

router = APIRouter(prefix="/properties", tags=["Properties"])

class SyncRequest(BaseModel):
    url: str = "https://tzelahahar.co.il/"

@router.post("/sync")
def trigger_sync(req: SyncRequest, db: Session = Depends(get_db)):
    """
    Synchronously syncs the provided URL to scrape property data.
    """
    try:
        results = sync_site(req.url, db)
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[PropertyRead])
def get_properties(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    props = db.query(Property).offset(skip).limit(limit).all()
    return props

@router.get("/{prop_id}", response_model=PropertyRead)
def get_property(prop_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop
