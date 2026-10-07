import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, defer

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import ContentItem, GeneratedMedia, Property, PropertyImage
from app.services.events import (
    PROMOTABLE_TYPES,
    SUPPORTED_LANGUAGES,
    SUPPORTED_PLATFORMS,
    get_default_language,
    get_mode,
    log_event,
)
from app.services.ingestion import sync_site

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["Properties"])


class SyncRequest(BaseModel):
    url: str = "https://tzelahahar.co.il/en/articles"


class ApproveRequest(BaseModel):
    language: Optional[str] = None          # target_language for the generated content


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class GenerateContentRequest(BaseModel):
    date: Optional[str] = None
    force: bool = False
    language: Optional[str] = None          # target_language: en | he
    kinds: Optional[List[str]] = None       # ["post"], ["story"] or both (default)
    variants: Optional[List[int]] = None    # 1..3 (post type / story variant)
    platform_targets: Optional[List[str]] = None


# ------------------------------------------------------------------------------ sync
@router.post("/sync")
def trigger_sync(req: SyncRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Scrape the given site/section. In AUTOMATION mode the full workflow runs afterwards."""
    try:
        results = sync_site(req.url, db)
    except Exception as e:
        log_event(db, "SCRAPE_FAILED", "site", None, "FAILED", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # Store the scraped images in GridFS right away (no AI, runs in the background) so cards show
    # real images immediately instead of waiting for approval.
    if results.get("property_ids"):
        bg.add_task(_store_images_bg, list(results["property_ids"]))

    results["automation_queued"] = 0
    results["automation_skipped"] = 0
    if get_mode(db) == "AUTOMATION":
        pending_ids = [
            row[0]
            for row in db.query(Property.id)
            .filter(Property.id.in_(results.get("property_ids", [])), Property.approval_status == "PENDING")
            .all()
        ]
        limit = getattr(get_settings(), "AUTOMATION_BATCH_LIMIT", 3)
        run, skipped = pending_ids[:limit], pending_ids[limit:]
        for property_id in skipped:
            log_event(db, "AUTO_APPROVED", "property", property_id, "SKIPPED",
                      error=f"Automation batch limit ({limit}) reached; approve manually or re-run")
        if run:
            bg.add_task(_run_automation_batch, run)
        results["automation_queued"] = len(run)
        results["automation_skipped"] = len(skipped)
    return {"status": "ok", "results": results}


# ------------------------------------------------------------------------------ read
def _summary(prop: Property, content_preview: Optional[str], preview: Optional[GeneratedMedia], counts: dict) -> dict:
    unloaded = sa_inspect(prop).unloaded  # heavy columns are deferred in the list query
    data = {c.name: getattr(prop, c.name) for c in prop.__table__.columns if c.key not in unloaded}
    # The list view only needs a short text; the full text is served by the detail endpoint.
    data["content"] = content_preview or None
    data.update(
        preview_url=preview.public_url if preview else None,
        preview_media_id=preview.id if preview else None,
        preview_status=None,
        content_counts=counts,
    )
    return data


@router.get("")
def get_properties(
    skip: int = 0,
    limit: int = 1000,
    approval_status: Optional[str] = None,
    include_other: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Property, func.substr(Property.content, 1, 400)).options(
        defer(Property.content), defer(Property.source_snapshot)
    )
    if not include_other:
        # Hide site navigation pages (contact, about, listing pages) that older scrapes stored.
        query = query.filter(Property.type.in_(PROMOTABLE_TYPES))
    if approval_status:
        query = query.filter(Property.approval_status == approval_status.upper())
    pairs = query.order_by(Property.scraped_at.desc().nullslast(), Property.id.desc()).offset(skip).limit(limit).all()
    if not pairs:
        return []
    props = [pair[0] for pair in pairs]
    previews_text = {pair[0].id: pair[1] for pair in pairs}
    ids = [p.id for p in props]

    previews: dict[int, GeneratedMedia] = {}
    rows = (
        db.query(PropertyImage, GeneratedMedia)
        .join(GeneratedMedia, PropertyImage.media_id == GeneratedMedia.id)
        .filter(PropertyImage.property_id.in_(ids), GeneratedMedia.generation_status == "COMPLETED")
        .order_by(PropertyImage.is_ai_generated.asc(), PropertyImage.id.asc())
        .all()
    )
    for pi, media in rows:
        previews.setdefault(pi.property_id, media)

    counts: dict[int, dict] = {}
    for pid, kind, n in (
        db.query(ContentItem.property_id, ContentItem.kind, func.count(ContentItem.id))
        .filter(ContentItem.property_id.in_(ids))
        .group_by(ContentItem.property_id, ContentItem.kind)
        .all()
    ):
        counts.setdefault(pid, {"post": 0, "story": 0})[kind] = n

    return [_summary(p, previews_text.get(p.id), previews.get(p.id), counts.get(p.id, {"post": 0, "story": 0})) for p in props]


@router.get("/{prop_id}")
def get_property(prop_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    image_data = []
    for pi in db.query(PropertyImage).filter(PropertyImage.property_id == prop_id).order_by(PropertyImage.id).all():
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == pi.media_id).first() if pi.media_id else None
        image_data.append({
            "id": pi.id,
            "source_url": pi.source_url,
            "status": pi.status,
            "failure_reason": pi.failure_reason,
            "is_ai_generated": pi.is_ai_generated,
            "media_id": media.id if media else None,
            "media_url": media.public_url if media and media.generation_status == "COMPLETED" else None,
            "media_status": media.generation_status if media else None,
        })

    data = {column.name: getattr(prop, column.name) for column in prop.__table__.columns}
    data["property_images"] = image_data
    data["content_counts"] = {
        kind: n
        for kind, n in db.query(ContentItem.kind, func.count(ContentItem.id))
        .filter(ContentItem.property_id == prop_id).group_by(ContentItem.kind).all()
    }
    return data


# ------------------------------------------------------------------------------ approve / reject
@router.post("/{prop_id}/approve")
def approve_property(
    prop_id: int,
    bg: BackgroundTasks,
    req: ApproveRequest = None,
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.approval_status == "REJECTED":
        raise HTTPException(status_code=409, detail="Cannot approve a rejected property")
    language = (req.language if req and req.language else None) or get_default_language(db)
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(422, "language must be 'en' or 'he'")
    if not (prop.name and (prop.description or prop.content)):
        raise HTTPException(422, "Property has no scraped text to promote")

    if prop.approval_status != "APPROVED":
        prop.approval_status = "APPROVED"
        prop.approved_at = datetime.now(timezone.utc)
        prop.rejected_at = None
        prop.rejection_reason = None
        log_event(db, "PROPERTY_APPROVED", "property", prop.id, "SUCCESS", language=language, commit=False)
    prop.content_generation_status = "PENDING"
    db.commit()

    # Validate/store images, then generate 3 posts + 3 stories (in the background).
    bg.add_task(_process_property_bg, prop_id, False, True, language)
    return get_property(prop_id, db)


@router.post("/{prop_id}/reject")
def reject_property(prop_id: int, req: RejectRequest = None, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    prop.approval_status = "REJECTED"
    prop.approved_at = None
    prop.rejected_at = datetime.now(timezone.utc)
    prop.rejection_reason = req.reason if req and req.reason else None
    db.commit()
    log_event(db, "PROPERTY_REJECTED", "property", prop.id, "SUCCESS", error=None)
    return get_property(prop_id, db)


@router.post("/{prop_id}/generate-content")
def generate_property_content(
    prop_id: int,
    req: GenerateContentRequest = None,
    db: Session = Depends(get_db),
):
    """Generate content now. Default = 3 posts + 3 stories; ``kinds``/``variants`` for manual runs."""
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.approval_status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Property must be approved before content generation. A rejected or pending property cannot generate content.",
        )
    req = req or GenerateContentRequest()
    if req.platform_targets and not set(req.platform_targets) <= set(SUPPORTED_PLATFORMS):
        raise HTTPException(422, "Unsupported platform in platform_targets")

    from app.services.content_generator import generate_content_for_property

    try:
        result = generate_content_for_property(
            prop, db, generation_date=req.date, force=req.force, language=req.language,
            kinds=req.kinds, variants=req.variants, platform_targets=req.platform_targets,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Content generation error for property {prop_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("skipped"):
        raise HTTPException(
            status_code=409,
            detail="This content already exists for the selected property, date and language. "
                   "Use Regenerate on the existing item to create a new version.",
        )
    return {"status": "ok", **result}


@router.post("/{prop_id}/validate-images")
def validate_property_images_endpoint(prop_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    bg.add_task(_validate_images_bg, prop_id, True)
    return {"status": "ok", "message": "Image validation started in background"}


# ------------------------------------------------------------------------------ background jobs
def _validate_images_bg(prop_id: int, force: bool = False):
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


def _store_images_bg(property_ids: list[int]) -> None:
    from concurrent.futures import ThreadPoolExecutor

    def one(property_id: int) -> None:
        db = SessionLocal()
        try:
            prop = db.query(Property).filter(Property.id == property_id).first()
            if prop and prop.approval_status != "REJECTED":
                from app.services.image_validator import validate_property_images

                validate_property_images(prop, db, allow_ai=False)
        except Exception as exc:
            logger.error("Image storing failed for property %s: %s", property_id, exc)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, property_ids))


def _run_automation_batch(property_ids: list[int]) -> None:
    for property_id in property_ids:
        _process_property_bg(property_id, True, True, None)


def _process_property_bg(
    prop_id: int, auto_approve: bool, generate_content: bool, language: Optional[str] = None
) -> None:
    """Store/validate media, optionally AI-validate + auto-approve, then run the 3+3 pipeline."""
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop:
            return
        from app.services.image_validator import validate_property_images

        validate_property_images(prop, db)
        if auto_approve and prop.approval_status == "PENDING":
            mode = "AUTOMATION"
            if not prop.name or not (prop.source_url or prop.url) or prop.media_status != "SUCCESS":
                log_event(db, "AUTO_APPROVED", "property", prop.id, "FAILED", mode=mode,
                          error="Property is missing a name, source URL, or usable media")
                return
            try:
                from app.services.ai_validation import validate_property_with_ai

                verdict = validate_property_with_ai(prop)
            except Exception as exc:
                log_event(db, "AUTO_APPROVED", "property", prop.id, "FAILED", mode=mode,
                          error=f"AI validation unavailable: {exc}")
                return
            if not verdict.suitable:
                log_event(db, "AUTO_APPROVED", "property", prop.id, "REJECTED_BY_AI", mode=mode,
                          error=verdict.reason)
                return
            prop.approval_status = "APPROVED"
            prop.approved_at = datetime.now(timezone.utc)
            db.commit()
            log_event(db, "AUTO_APPROVED", "property", prop.id, "SUCCESS", mode=mode,
                      language=prop.language)

        if generate_content and prop.approval_status == "APPROVED":
            from app.services.content_generator import generate_content_for_property

            generate_content_for_property(prop, db, language=language)
    except Exception as exc:
        logger.exception("Property processing failed for %s", prop_id)
        try:
            db.rollback()
            prop = db.query(Property).filter(Property.id == prop_id).first()
            if prop and prop.content_generation_status in ("PENDING", "PROCESSING"):
                prop.content_generation_status = "FAILED"
                db.commit()
            log_event(db, "CONTENT_GENERATION_FAILED", "property", prop_id, "FAILED", error=str(exc))
        except Exception:
            db.rollback()
    finally:
        db.close()
