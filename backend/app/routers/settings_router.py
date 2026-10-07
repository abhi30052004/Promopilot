from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.database import get_db
from app.models import Setting

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("")
def get_all_settings(db: Session = Depends(get_db)):
    settings_db = db.query(Setting).all()
    return {s.key: s.value for s in settings_db}

@router.put("")
def update_settings(updates: Dict[str, Any], db: Session = Depends(get_db)):
    for k, v in updates.items():
        s = db.query(Setting).filter(Setting.key == k).first()
        if s:
            s.value = v
        else:
            s = Setting(key=k, value=v)
            db.add(s)
    db.commit()
    return {"status": "ok"}
