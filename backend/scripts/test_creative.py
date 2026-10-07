import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ContentItem, Property
from app.services.creative import render_creative

def test_creative():
    db = SessionLocal()
    
    prop = Property(name="Test Villa", type="villa", location="North", images=[])
    db.add(prop)
    db.commit()
    db.refresh(prop)
    
    post = ContentItem(
        property_id=prop.id,
        kind="post",
        caption="חופשה מושלמת בצפון הארץ! \n בואו להנות מנוף עוצר נשימה ווילה יוקרתית.",
        platform="instagram",
        status="draft"
    )
    
    story = ContentItem(
        property_id=prop.id,
        kind="story",
        caption="חופשה מושלמת בצפון הארץ!",
        platform="instagram",
        status="draft"
    )
    
    db.add(post)
    db.add(story)
    db.commit()
    db.refresh(post)
    db.refresh(story)
    
    print("Generating post creative...")
    post_path = render_creative(post, prop)
    print(f"Post creative saved to MEDIA_DIR/{post_path}")
    
    print("Generating story creative...")
    story_path = render_creative(story, prop)
    print(f"Story creative saved to MEDIA_DIR/{story_path}")
    
    db.delete(post)
    db.delete(story)
    db.delete(prop)
    db.commit()
    db.close()

if __name__ == "__main__":
    test_creative()
