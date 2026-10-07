import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from ..database import get_db, SessionLocal
from ..models import Property, PropertyImage, GeneratedMedia, AutomationLog, Setting
from ..schemas import PropertyRead
from ..services.ingestion import sync_site

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["Properties"])


class SyncRequest(BaseModel):
    url: str = "https://tzelahahar.co.il/"


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class GenerateContentRequest(BaseModel):
    date: Optional[str] = None
    force: bool = False


@router.post("/sync")
def trigger_sync(req: SyncRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Synchronously syncs the provided URL to scrape property data."""
    try:
        results = sync_site(req.url, db)
        mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
        automatic = bool(mode_row and str(mode_row.value).upper() == "AUTOMATION")
        for property_id in results.get("property_ids", []):
            bg.add_task(_process_property_bg, property_id, automatic, automatic)
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def get_properties(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    props = db.query(Property).offset(skip).limit(limit).all()
    return [_property_summary(prop, db) for prop in props]


def _property_summary(prop: Property, db: Session) -> dict:
    preview = (
        db.query(PropertyImage, GeneratedMedia)
        .join(GeneratedMedia, PropertyImage.media_id == GeneratedMedia.id)
        .filter(
            PropertyImage.property_id == prop.id,
            GeneratedMedia.generation_status == "COMPLETED",
        )
        .order_by(PropertyImage.is_ai_generated.asc(), PropertyImage.id.asc())
        .first()
    )
    return {
        column.name: getattr(prop, column.name) for column in prop.__table__.columns
    } | {
        "preview_url": preview[1].storage_url if preview else None,
        "preview_status": preview[0].status if preview else None,
    }


@router.get("/{prop_id}")
def get_property(prop_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Include image status
    images = db.query(PropertyImage).filter(PropertyImage.property_id == prop_id).all()
    image_data = []
    for pi in images:
        media = None
        if pi.media_id:
            media = db.query(GeneratedMedia).filter(GeneratedMedia.id == pi.media_id).first()
        image_data.append({
            "id": pi.id,
            "source_url": pi.source_url,
            "status": pi.status,
            "failure_reason": pi.failure_reason,
            "is_ai_generated": pi.is_ai_generated,
            "media_url": media.storage_url if media else None,
        })

    return {
        "id": prop.id,
        "name": prop.name,
        "slug": prop.slug,
        "type": prop.type,
        "description": prop.description,
        "amenities": prop.amenities,
        "location": prop.location,
        "url": prop.url,
        "source_url": prop.source_url,
        "title": prop.title,
        "images": prop.images,
        "last_synced_at": prop.last_synced_at,
        "created_at": prop.created_at,
        "updated_at": prop.updated_at,
        "approval_status": prop.approval_status,
        "approved_at": prop.approved_at,
        "rejected_at": prop.rejected_at,
        "rejection_reason": prop.rejection_reason,
        "media_status": prop.media_status,
        "content_generation_status": prop.content_generation_status,
        "scraped_at": prop.scraped_at,
        "price": prop.price,
        "category": prop.category,
        "property_images": image_data,
    }


@router.post("/{prop_id}/approve")
def approve_property(prop_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.approval_status == "APPROVED":
        return get_property(prop_id, db)
    if prop.approval_status == "REJECTED":
        raise HTTPException(status_code=409, detail="Cannot approve a rejected property")

    prop.approval_status = "APPROVED"
    prop.approved_at = datetime.now(timezone.utc)
    db.commit()

    # Trigger image validation in background
    bg.add_task(_process_property_bg, prop_id, False, True)

    # Log if automation mode
    s = db.query(Setting).filter(Setting.key == "approval_mode").first()
    mode = s.value if s else "HUMAN"
    db.add(AutomationLog(
        action="PROPERTY_APPROVED",
        entity_type="property",
        entity_id=prop.id,
        mode=mode,
        status="SUCCESS",
    ))
    db.commit()

    return get_property(prop_id, db)


@router.post("/{prop_id}/reject")
def reject_property(prop_id: int, req: RejectRequest = None, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    prop.approval_status = "REJECTED"
    prop.approved_at = None
    prop.rejected_at = datetime.now(timezone.utc)
    if req and req.reason:
        prop.rejection_reason = req.reason
    mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
    db.add(AutomationLog(
        action="PROPERTY_REJECTED",
        entity_type="property",
        entity_id=prop.id,
        mode=mode_row.value if mode_row else "HUMAN",
        status="SUCCESS",
    ))
    db.commit()
    return get_property(prop_id, db)


@router.post("/{prop_id}/generate-content")
def generate_property_content(
    prop_id: int,
    req: GenerateContentRequest = None,
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Hard guard
    if prop.approval_status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Property must be approved before content generation. A rejected property can never generate content.",
        )

    from ..services.content_generator import generate_content_for_property

    req_date = req.date if req else None
    force = req.force if req else False

    try:
        result = generate_content_for_property(prop, db, generation_date=req_date, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Content generation error for property {prop_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", **result}


@router.post("/{prop_id}/validate-images")
def validate_property_images_endpoint(prop_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    bg.add_task(_validate_images_bg, prop_id, True)
    return {"status": "ok", "message": "Image validation started in background"}


def _validate_images_bg(prop_id: int, force: bool = False):
    """Background task to validate images for a property."""
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop:
            return
        from app.services.image_validator import validate_property_images
        validate_property_images(prop, db, force=force)
    except Exception as exc:
        logger.error(f"Background image validation failed for property {prop_id}: {exc}")
    finally:
        db.close()


def _process_property_bg(prop_id: int, auto_approve: bool, generate_content: bool) -> None:
    """Validate media, optionally auto-approve, then run the 3+3 content pipeline."""
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop:
            return
        from app.services.image_validator import validate_property_images

        validate_property_images(prop, db)
        if auto_approve and prop.approval_status == "PENDING":
            # Eligibility is deliberately factual and deterministic: a scraped item must
            # have a name and a source URL. AI never invents missing property details.
            if not prop.name or not (prop.source_url or prop.url) or prop.media_status != "SUCCESS":
                db.add(AutomationLog(
                    action="PROPERTY_AUTO_APPROVED",
                    entity_type="property",
                    entity_id=prop.id,
                    mode="AUTOMATION",
                    status="FAILED",
                    error="Property is missing a name, source URL, or usable media",
                ))
                db.commit()
                return
            prop.approval_status = "APPROVED"
            prop.approved_at = datetime.now(timezone.utc)
            db.add(AutomationLog(
                action="PROPERTY_AUTO_APPROVED",
                entity_type="property",
                entity_id=prop.id,
                mode="AUTOMATION",
                status="SUCCESS",
            ))
            db.commit()

        if generate_content and prop.approval_status == "APPROVED":
            from app.services.content_generator import generate_content_for_property

            generate_content_for_property(prop, db)
    except Exception as exc:
        logger.exception("Property processing failed for %s", prop_id)
        try:
            db.add(AutomationLog(
                action="CONTENT_GENERATED" if generate_content else "IMAGE_GENERATION_FAILED",
                entity_type="property",
                entity_id=prop_id,
                mode="AUTOMATION" if auto_approve else "HUMAN",
                status="FAILED",
                error=str(exc),
            ))
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
