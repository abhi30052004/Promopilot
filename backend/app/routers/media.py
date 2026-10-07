"""
Media router - Milestone 5.
GET /api/media/{id}
POST /api/media/generate-image
POST /api/media/generate-video
"""
import logging
import threading
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import math

from app.database import get_db, SessionLocal
from app.models import AutomationLog, GeneratedMedia, ContentItem, Property, Setting
from app.services.media_storage import complete_media, create_pending_media, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["Media"])
public_router = APIRouter(prefix="/media", tags=["Media"])

class GenerateImageRequest(BaseModel):
    property_id: int
    content_id: Optional[int] = None
    force: bool = False

class GenerateVideoRequest(BaseModel):
    content_id: int
    force: bool = False

@router.get("/usage")
def get_media_usage(db: Session = Depends(get_db)):
    """Return storage usage stats."""
    from app.config import get_settings
    s = get_settings()
    
    total_bytes = db.query(GeneratedMedia.size_bytes).filter(GeneratedMedia.size_bytes != None).all()
    used_mb = sum([b[0] for b in total_bytes]) / (1024 * 1024)
    file_count = db.query(GeneratedMedia).count()
    
    return {
        "used_mb": round(used_mb, 2),
        "cap_mb": s.MEDIA_MAX_TOTAL_MB,
        "file_count": file_count,
        "percent_used": round((used_mb / s.MEDIA_MAX_TOTAL_MB) * 100, 2) if s.MEDIA_MAX_TOTAL_MB else 0
    }

@public_router.get("/{media_id}/file")
def stream_media_file(media_id: int, request: Request, t: str, db: Session = Depends(get_db)):
    """Public route to stream GridFS media with HTTP Range support."""
    media = db.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).first()
    if not media or media.file_token != t:
        raise HTTPException(404, "Not found")

    storage = get_storage()
    if not media.storage_key:
        raise HTTPException(404, "Not found")

    try:
        grid_out, length, stored_mime_type = storage.open_stream(media.storage_key)
    except Exception:
        raise HTTPException(404, "File not found in storage")

    range_header = request.headers.get('Range')
    
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f'"{media.sha256}"'
    }

    if range_header:
        # e.g. bytes=0-1023
        try:
            byte_range = range_header.replace('bytes=', '').split('-')
            start = int(byte_range[0])
            end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else length - 1
        except ValueError:
            start, end = 0, length - 1
            
        if start >= length:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{length}"})

        end = min(end, length - 1)
        chunk_size = end - start + 1
        
        headers["Content-Range"] = f"bytes {start}-{end}/{length}"
        headers["Content-Length"] = str(chunk_size)
        headers["Content-Type"] = media.mime_type or stored_mime_type

        def iterfile():
            grid_out.seek(start)
            remaining = chunk_size
            while remaining > 0:
                read_size = min(remaining, 1024 * 64)
                chunk = grid_out.read(read_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
            grid_out.close()

        return StreamingResponse(iterfile(), status_code=206, headers=headers)
    else:
        headers["Content-Length"] = str(length)
        headers["Content-Type"] = media.mime_type or stored_mime_type

        def iterfile():
            while True:
                chunk = grid_out.read(1024 * 64)
                if not chunk:
                    break
                yield chunk
            grid_out.close()

        return StreamingResponse(iterfile(), status_code=200, headers=headers)



@router.get("/{media_id}")
def get_media(media_id: int, db: Session = Depends(get_db)):
    media = db.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).first()
    if not media:
        raise HTTPException(404, "Media not found")
    return {
        "id": media.id,
        "property_id": media.property_id,
        "content_id": media.content_id,
        "media_type": media.media_type,
        "provider": media.provider,
        "storage_url": media.storage_url,
        "thumbnail_url": media.thumbnail_url,
        "mime_type": media.mime_type,
        "width": media.width,
        "height": media.height,
        "duration_seconds": media.duration_seconds,
        "generation_status": media.generation_status,
        "is_ai_generated": media.is_ai_generated,
        "error": media.error,
        "created_at": media.created_at,
        "updated_at": media.updated_at,
    }


@router.post("/generate-image")
def generate_image(req: GenerateImageRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a background job to generate an AI image for a property."""
    prop = db.query(Property).filter(Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(404, "Property not found")

    if req.content_id:
        item = db.query(ContentItem).filter(ContentItem.id == req.content_id).first()
        if not item or item.property_id != req.property_id:
            raise HTTPException(400, "content_id does not belong to property_id")
    if not req.force:
        existing = db.query(GeneratedMedia).filter(
            GeneratedMedia.property_id == req.property_id,
            GeneratedMedia.content_id == req.content_id,
            GeneratedMedia.media_type == "IMAGE",
            GeneratedMedia.provider == "OPENAI",
            GeneratedMedia.generation_status.in_(["PENDING", "GENERATING", "COMPLETED"]),
        ).order_by(GeneratedMedia.created_at.desc()).first()
        if existing:
            return {"status": "ok", "media_id": existing.id, "generation_status": existing.generation_status}

    media = create_pending_media(
        db,
        property_id=req.property_id,
        content_id=req.content_id,
        media_type="IMAGE",
        provider="OPENAI",
        mime_type="image/jpeg",
        is_ai=True,
    )

    bg.add_task(_generate_image_bg, media.id, req.property_id)

    return {"status": "ok", "media_id": media.id, "generation_status": "PENDING"}


@router.post("/generate-video")
def generate_video(req: GenerateVideoRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a background job to generate a story video."""
    item = db.query(ContentItem).filter(ContentItem.id == req.content_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
    if item.kind != "story":
        raise HTTPException(400, "Video generation is only for story items")

    from app.services.video_generator import queue_story_video
    from app.services.content_generator import _pick_best_image

    source = _pick_best_image(item.property, db) if item.property else None
    media = queue_story_video(item, source.id if source else None, db, force=req.force)

    return {"status": "ok", "media_id": media.id, "generation_status": media.generation_status}


def _generate_image_bg(media_id: int, property_id: int):
    db = SessionLocal()
    try:
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).first()
        prop = db.query(Property).filter(Property.id == property_id).first()
        if not media or not prop:
            return

        media.generation_status = "GENERATING"
        mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
        db.add(AutomationLog(
            action="IMAGE_GENERATION_STARTED",
            entity_type="generated_media",
            entity_id=media.id,
            mode=mode_row.value if mode_row else "HUMAN",
            status="STARTED",
        ))
        db.commit()

        from app.services.image_validator import _generate_ai_image, _build_image_prompt

        img_data = _generate_ai_image(prop)
        media.prompt = _build_image_prompt(prop)
        complete_media(db, media, img_data, mime_type="image/png", ext="png")
        if media.content_id:
            item = db.query(ContentItem).filter(ContentItem.id == media.content_id).first()
            if item:
                item.media_id = media.id
        db.add(AutomationLog(
            action="IMAGE_GENERATED",
            entity_type="generated_media",
            entity_id=media.id,
            mode=mode_row.value if mode_row else "HUMAN",
            status="SUCCESS",
        ))
        db.commit()
    except Exception as exc:
        logger.error(f"BG image generation failed for media {media_id}: {exc}")
        try:
            media = db.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).first()
            if media:
                media.generation_status = "FAILED"
                media.error = str(exc)
                mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
                db.add(AutomationLog(
                    action="IMAGE_GENERATION_FAILED",
                    entity_type="generated_media",
                    entity_id=media.id,
                    mode=mode_row.value if mode_row else "HUMAN",
                    status="FAILED",
                    error=str(exc),
                ))
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


