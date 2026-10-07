"""Persistent media storage abstraction.

The database stores metadata and a tokenized application URL; binary payloads live
in local storage (development), S3-compatible object storage, or MongoDB GridFS.
"""
from __future__ import annotations

import hashlib
import io
import logging
import mimetypes
import secrets
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)


class MediaStorage(ABC):
    @abstractmethod
    def upload(
        self, data: bytes, filename: str, mime_type: str, metadata: dict
    ) -> Tuple[str, int]:
        """Upload bytes and return ``(storage_key, size_bytes)``."""

    @abstractmethod
    def open_stream(self, storage_key: str) -> Tuple[Any, int, str]:
        """Return a readable stream, byte length, and MIME type."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete an object when it exists."""

    def exists(self, storage_key: str) -> bool:
        """True when the stored object can be opened (used to detect lost media)."""
        try:
            stream, _length, _mime = self.open_stream(storage_key)
        except Exception:
            return False
        close = getattr(stream, "close", None)
        if close:
            close()
        return True


class LocalStorage(MediaStorage):
    def __init__(self, media_dir: str):
        self.media_dir = Path(media_dir).resolve()
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        candidate = (self.media_dir / storage_key).resolve()
        if self.media_dir not in candidate.parents:
            raise ValueError("Invalid media storage key")
        return candidate

    def upload(
        self, data: bytes, filename: str, mime_type: str, metadata: dict
    ) -> Tuple[str, int]:
        key = f"{uuid.uuid4().hex}_{Path(filename).name}"
        self._path(key).write_bytes(data)
        return key, len(data)

    def open_stream(self, storage_key: str) -> Tuple[Any, int, str]:
        path = self._path(storage_key)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path.open("rb"), path.stat().st_size, mime_type

    def delete(self, storage_key: str) -> None:
        try:
            self._path(storage_key).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Local media delete failed for %s: %s", storage_key, exc)


class S3Storage(MediaStorage):
    def __init__(self, bucket: str, region: Optional[str], endpoint: Optional[str], prefix: str):
        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3", region_name=region or None, endpoint_url=endpoint or None
        )

    def upload(
        self, data: bytes, filename: str, mime_type: str, metadata: dict
    ) -> Tuple[str, int]:
        prefix = f"{self.prefix}/" if self.prefix else ""
        key = f"{prefix}{uuid.uuid4().hex}_{Path(filename).name}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=mime_type,
            Metadata={str(k): str(v) for k, v in metadata.items()},
        )
        return key, len(data)

    def open_stream(self, storage_key: str) -> Tuple[Any, int, str]:
        obj = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        data = obj["Body"].read()
        return io.BytesIO(data), len(data), obj.get("ContentType") or "application/octet-stream"

    def delete(self, storage_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)


class MongoGridFSStorage(MediaStorage):
    def __init__(self, uri: str, db_name: str):
        import gridfs
        from pymongo import MongoClient

        # mongodb+srv:// needs a DNS SRV lookup that is occasionally slow/flaky on
        # developer networks, so connect with a few retries before giving up.
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                self.client = MongoClient(
                    uri, serverSelectionTimeoutMS=20000, retryWrites=True, appname="promopilot"
                )
                self.client.admin.command("ping")
                break
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
                logger.warning("MongoDB connect attempt %s failed: %s", attempt, exc)
        else:
            raise RuntimeError(f"Could not connect to MongoDB GridFS: {last_error}")
        self.db = self.client[db_name]
        # Default GridFS bucket => collections fs.files / fs.chunks (per spec).
        self.fs = gridfs.GridFSBucket(self.db, bucket_name="fs")
        self.db["fs.files"].create_index("metadata.media_id")

    def upload(
        self, data: bytes, filename: str, mime_type: str, metadata: dict
    ) -> Tuple[str, int]:
        file_id = self.fs.upload_from_stream(
            filename, data, metadata={**metadata, "mime_type": mime_type}
        )
        return str(file_id), len(data)

    def open_stream(self, storage_key: str) -> Tuple[Any, int, str]:
        from bson import ObjectId

        grid_out = self.fs.open_download_stream(ObjectId(storage_key))
        mime_type = (grid_out.metadata or {}).get("mime_type", "application/octet-stream")
        return grid_out, grid_out.length, mime_type

    def delete(self, storage_key: str) -> None:
        from bson import ObjectId

        self.fs.delete(ObjectId(storage_key))


_storage_instance: Optional[MediaStorage] = None
_storage_signature: Optional[tuple] = None


def get_storage() -> MediaStorage:
    global _storage_instance, _storage_signature
    settings = get_settings()
    backend = settings.STORAGE_BACKEND.lower().strip()
    signature = (
        backend,
        settings.MEDIA_DIR,
        settings.MONGODB_URI,
        settings.mongo_db_name,
        settings.S3_BUCKET,
        settings.S3_REGION,
        settings.S3_ENDPOINT_URL,
        settings.S3_PREFIX,
    )
    if _storage_instance is not None and signature == _storage_signature:
        return _storage_instance

    if backend == "local":
        instance: MediaStorage = LocalStorage(settings.MEDIA_DIR)
    elif backend == "s3":
        if not settings.S3_BUCKET:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        instance = S3Storage(
            settings.S3_BUCKET,
            settings.S3_REGION,
            settings.S3_ENDPOINT_URL,
            settings.S3_PREFIX,
        )
    elif backend == "mongo":
        if not settings.MONGODB_URI:
            raise RuntimeError("MONGODB_URI is required when STORAGE_BACKEND=mongo")
        instance = MongoGridFSStorage(settings.MONGODB_URI, settings.mongo_db_name)
    else:
        raise RuntimeError("STORAGE_BACKEND must be one of: local, s3, mongo")

    _storage_instance = instance
    _storage_signature = signature
    return instance


def optimize_image_bytes(data: bytes, mime_type: str) -> Tuple[bytes, str, int, int]:
    """Decode, normalize, and cap image dimensions before persistent storage."""
    if not mime_type.startswith("image/"):
        return data, mime_type, 0, 0
    from PIL import Image

    image = Image.open(io.BytesIO(data))
    image.load()
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    if max(width, height) > 1600:
        ratio = 1600 / max(width, height)
        width, height = int(width * ratio), int(height * ratio)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue(), "image/jpeg", width, height


def public_media_url(media_id: int, file_token: str) -> str:
    base = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
    return f"{base}/api/media/{media_id}?t={file_token}"


def create_pending_media(
    db,
    *,
    property_id: Optional[int],
    content_id: Optional[int],
    media_type: str,
    provider: str,
    mime_type: Optional[str] = None,
    prompt: Optional[str] = None,
    is_ai: bool = False,
):
    from app.models import GeneratedMedia

    media = GeneratedMedia(
        property_id=property_id,
        content_id=content_id,
        media_type=media_type,
        provider=provider,
        prompt=prompt,
        mime_type=mime_type,
        generation_status="PENDING",
        is_ai_generated=is_ai,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def complete_media(
    db,
    media,
    data: bytes,
    *,
    mime_type: str,
    ext: str,
    width: int = 0,
    height: int = 0,
    duration: int = 0,
):
    """Upload bytes and complete an existing GeneratedMedia state record."""
    media.generation_status = "GENERATING"
    media.error = None
    db.commit()
    try:
        if media.media_type == "IMAGE":
            data, mime_type, width, height = optimize_image_bytes(data, mime_type)
            ext = "jpg"
        token = media.file_token or secrets.token_urlsafe(32)
        filename = f"{media.property_id or 'none'}_{media.id}.{ext}"
        storage_key, size_bytes = get_storage().upload(
            data,
            filename,
            mime_type,
            metadata={
                "media_id": media.id,
                "property_id": media.property_id or "",
                "content_id": media.content_id or "",
            },
        )
        media.storage_key = storage_key
        media.file_name = filename
        media.size_bytes = size_bytes
        media.file_token = token
        media.sha256 = hashlib.sha256(data).hexdigest()
        media.storage_url = public_media_url(media.id, token)
        media.mime_type = mime_type
        media.width = width or None
        media.height = height or None
        media.duration_seconds = duration or None
        media.generation_status = "COMPLETED"
        db.commit()
        db.refresh(media)
        return media
    except Exception as exc:
        media.generation_status = "FAILED"
        media.error = str(exc)
        db.commit()
        raise


def save_generated_media(
    db,
    data: bytes,
    property_id: Optional[int],
    content_id: Optional[int],
    media_type: str,
    provider: str,
    mime_type: str,
    ext: str,
    width: int = 0,
    height: int = 0,
    duration: int = 0,
    prompt: Optional[str] = None,
    is_ai: bool = False,
):
    media = create_pending_media(
        db,
        property_id=property_id,
        content_id=content_id,
        media_type=media_type,
        provider=provider,
        mime_type=mime_type,
        prompt=prompt,
        is_ai=is_ai,
    )
    return complete_media(
        db,
        media,
        data,
        mime_type=mime_type,
        ext=ext,
        width=width,
        height=height,
        duration=duration,
    )


def read_media_bytes(media) -> bytes:
    if not media or not media.storage_key:
        raise FileNotFoundError("Media has no storage key")
    stream, _length, _mime = get_storage().open_stream(media.storage_key)
    try:
        return stream.read()
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()
