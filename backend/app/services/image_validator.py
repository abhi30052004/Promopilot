"""Validate scraped images and generate contextual OpenAI fallbacks."""
from __future__ import annotations

import base64
import io
import logging
import socket
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AutomationLog, GeneratedMedia, Property, PropertyImage, Setting
from app.services.media_storage import save_generated_media

logger = logging.getLogger(__name__)
settings = get_settings()

_BLOCKED_NETS = tuple(
    ip_network(value)
    for value in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)
_MAX_SIZE_BYTES = 10 * 1024 * 1024
_TIMEOUT = 10.0
_MAX_REDIRECTS = 3
_MIN_WIDTH = 400
_TRUSTED_IMAGE_HOST_SUFFIXES = (".supabase.co",)


def _log(
    db: Session,
    action: str,
    entity_id: int,
    status: str,
    error: str | None = None,
    entity_type: str = "property",
) -> None:
    mode_row = db.query(Setting).filter(Setting.key == "approval_mode").first()
    db.add(
        AutomationLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            mode=(mode_row.value if mode_row else "HUMAN"),
            status=status,
            error=error,
        )
    )
    db.commit()


def _is_safe_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"scheme {parsed.scheme!r} not allowed"
    if not parsed.hostname:
        return False, "missing host"
    # The configured source stores public property images in Supabase. In
    # proxied production/sandbox environments local DNS can be unavailable even
    # though the HTTPS proxy can safely fetch this well-known public suffix.
    if any(parsed.hostname.endswith(suffix) for suffix in _TRUSTED_IMAGE_HOST_SUFFIXES):
        return True, ""
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except Exception as exc:
        return False, f"DNS resolution failed: {exc}"
    for address in addresses:
        try:
            resolved = ip_address(address[4][0])
        except ValueError:
            continue
        if any(resolved in network for network in _BLOCKED_NETS):
            return False, f"private address {resolved} is not allowed"
    return True, ""


def _browser_headers(referer: Optional[str] = None) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _decode_image(data: bytes) -> tuple[int, int]:
    if not data:
        raise ValueError("empty response")
    if len(data) > _MAX_SIZE_BYTES:
        raise ValueError(f"image exceeds {_MAX_SIZE_BYTES} bytes")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        width, height = image.size
    if width < _MIN_WIDTH:
        raise ValueError(f"image is only {width}px wide")
    return width, height


def _validate_and_download(
    image_url: str, source_site: Optional[str] = None
) -> tuple[Optional[bytes], Optional[str], str]:
    """Return ``(bytes, mime_type, failure_reason)`` without following unsafe redirects."""
    current = image_url
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                safe, reason = _is_safe_url(current)
                if not safe:
                    return None, None, f"SSRF blocked: {reason}"
                response = client.get(current, headers=_browser_headers(source_site))
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        return None, None, "redirect without Location header"
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    return None, None, f"HTTP {response.status_code}"
                mime_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if not mime_type.startswith("image/"):
                    return None, None, f"content type {mime_type!r} is not an image"
                _decode_image(response.content)
                return response.content, mime_type, ""
        return None, None, "too many redirects"
    except httpx.TimeoutException:
        return None, None, "timeout"
    except Exception as exc:
        return None, None, str(exc)


def _read_legacy_local_image(relative_path: str) -> tuple[Optional[bytes], Optional[str], str]:
    media_root = Path(settings.MEDIA_DIR).resolve()
    path = (media_root / relative_path.lstrip("/\\")).resolve()
    if media_root not in path.parents or not path.is_file():
        return None, None, "local image is unavailable"
    try:
        data = path.read_bytes()
        _decode_image(data)
        suffix = path.suffix.lower().lstrip(".") or "jpeg"
        if suffix == "jpg":
            suffix = "jpeg"
        return data, f"image/{suffix}", ""
    except Exception as exc:
        return None, None, str(exc)


def _build_image_prompt(prop: Property) -> str:
    amenities = prop.amenities or []
    if isinstance(amenities, list):
        amenities_text = ", ".join(str(value) for value in amenities[:15])
    else:
        amenities_text = str(amenities)
    return (
        "Create a realistic premium tourism photograph based only on the supplied property "
        "information. Do not invent identifiable facts or specific architecture that is not "
        "described. Do not add text, logos, watermarks, or fake signage. "
        f"Property: {prop.name}. "
        f"Location: {prop.location or 'not specified'}. "
        f"Category: {prop.category or prop.type or 'vacation property'}. "
        f"Description: {(prop.description or 'not specified')[:600]}. "
        f"Amenities: {amenities_text or 'not specified'}. "
        "Create a realistic travel and tourism promotional photograph with natural lighting."
    )


def _generate_ai_image(prop: Property) -> bytes:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI

    response = OpenAI(api_key=settings.OPENAI_API_KEY).images.generate(
        model=settings.IMAGE_MODEL or settings.OPENAI_IMAGE_MODEL or "gpt-image-1",
        prompt=_build_image_prompt(prop),
        n=1,
        size="1024x1024",
    )
    image = response.data[0]
    if getattr(image, "b64_json", None):
        return base64.b64decode(image.b64_json)
    if getattr(image, "url", None):
        response = httpx.get(image.url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        _decode_image(response.content)
        return response.content
    raise RuntimeError("OpenAI image response did not contain image data")


def _max_ai_images(db: Session) -> int:
    row = db.query(Setting).filter(Setting.key == "max_ai_images_per_property").first()
    return int(row.value if row and row.value is not None else settings.MAX_AI_IMAGES_PER_PROPERTY)


def _make_ai_fallback(prop: Property, db: Session, image_row: PropertyImage) -> bool:
    current_count = (
        db.query(GeneratedMedia)
        .filter(
            GeneratedMedia.property_id == prop.id,
            GeneratedMedia.media_type == "IMAGE",
            GeneratedMedia.is_ai_generated.is_(True),
        )
        .count()
    )
    if current_count >= _max_ai_images(db):
        return False
    _log(db, "IMAGE_GENERATION_STARTED", prop.id, "STARTED")
    try:
        data = _generate_ai_image(prop)
        media = save_generated_media(
            db=db,
            data=data,
            property_id=prop.id,
            content_id=None,
            media_type="IMAGE",
            provider="OPENAI",
            prompt=_build_image_prompt(prop),
            mime_type="image/png",
            ext="png",
            is_ai=True,
        )
        image_row.media_id = media.id
        image_row.is_ai_generated = True
        db.commit()
        _log(db, "IMAGE_GENERATED", media.id, "SUCCESS", entity_type="generated_media")
        return True
    except Exception as exc:
        logger.error("AI replacement failed for property %s: %s", prop.id, exc)
        _log(db, "IMAGE_GENERATION_FAILED", prop.id, "FAILED", str(exc))
        return False


def validate_property_images(prop: Property, db: Session, force: bool = False) -> None:
    """Validate every source image and persist every usable original or AI replacement."""
    sources = list(dict.fromkeys(prop.images or []))
    prop.media_status = "PROCESSING"
    db.commit()

    if not sources:
        placeholder = (
            db.query(PropertyImage)
            .filter(PropertyImage.property_id == prop.id, PropertyImage.source_url.is_(None))
            .first()
        )
        if not placeholder:
            placeholder = PropertyImage(
                property_id=prop.id,
                status="BROKEN",
                failure_reason="No scraped image was available",
                checked_at=datetime.now(timezone.utc),
            )
            db.add(placeholder)
            db.commit()
            db.refresh(placeholder)
        if not placeholder.media_id or force:
            _make_ai_fallback(prop, db, placeholder)

    for source in sources:
        image_row = (
            db.query(PropertyImage)
            .filter(PropertyImage.property_id == prop.id, PropertyImage.source_url == source)
            .first()
        )
        if not image_row:
            image_row = PropertyImage(property_id=prop.id, source_url=source, status="PENDING")
            db.add(image_row)
            db.commit()
            db.refresh(image_row)
        elif not force and image_row.media_id:
            media = db.query(GeneratedMedia).filter(GeneratedMedia.id == image_row.media_id).first()
            if media and media.generation_status == "COMPLETED":
                continue

        if source.startswith(("http://", "https://")):
            data, mime_type, reason = _validate_and_download(source, prop.source_url or prop.url)
        else:
            data, mime_type, reason = _read_legacy_local_image(source)

        if data and mime_type:
            try:
                extension = mime_type.split("/", 1)[1].replace("jpeg", "jpg")
                media = save_generated_media(
                    db=db,
                    data=data,
                    property_id=prop.id,
                    content_id=None,
                    media_type="IMAGE",
                    provider="SCRAPED",
                    mime_type=mime_type,
                    ext=extension,
                    is_ai=False,
                )
                image_row.status = "VALID"
                image_row.failure_reason = None
                image_row.media_id = media.id
                image_row.is_ai_generated = False
            except Exception as exc:
                data = None
                reason = f"storage failed: {exc}"

        if not data:
            image_row.status = "BROKEN"
            image_row.failure_reason = reason
            image_row.media_id = None
            image_row.is_ai_generated = False
            db.commit()
            _make_ai_fallback(prop, db, image_row)

        image_row.checked_at = datetime.now(timezone.utc)
        db.commit()

    usable = (
        db.query(PropertyImage)
        .join(GeneratedMedia, PropertyImage.media_id == GeneratedMedia.id)
        .filter(
            PropertyImage.property_id == prop.id,
            GeneratedMedia.generation_status == "COMPLETED",
            GeneratedMedia.storage_url.is_not(None),
        )
        .count()
    )
    prop.media_status = "SUCCESS" if usable else "FAILED"
    db.commit()


def ensure_at_least_one_image(prop: Property, db: Session) -> Optional[GeneratedMedia]:
    media = (
        db.query(GeneratedMedia)
        .filter(
            GeneratedMedia.property_id == prop.id,
            GeneratedMedia.media_type == "IMAGE",
            GeneratedMedia.generation_status == "COMPLETED",
            GeneratedMedia.storage_url.is_not(None),
        )
        .order_by(GeneratedMedia.is_ai_generated.asc(), GeneratedMedia.created_at.asc())
        .first()
    )
    if media:
        return media
    validate_property_images(prop, db, force=True)
    return (
        db.query(GeneratedMedia)
        .filter(
            GeneratedMedia.property_id == prop.id,
            GeneratedMedia.media_type == "IMAGE",
            GeneratedMedia.generation_status == "COMPLETED",
        )
        .first()
    )
