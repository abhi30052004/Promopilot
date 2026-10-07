from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import Property

def get_property_context(property_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """
    Returns verified facts for the writer to use when generating content.
    """
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return None
        
    return {
        "name": prop.name,
        "type": prop.type,
        "location": prop.location,
        "description": prop.description,
        "amenities": prop.amenities,
        "url": prop.url
    }
