import os
import sys
import hashlib
import secrets
from urllib.parse import urlparse
import httpx
import logging

# Ensure we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import GeneratedMedia
from app.services.media_storage import get_storage
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    settings = get_settings()
    db = SessionLocal()
    try:
        storage = get_storage()
        if not getattr(storage, "fs", None):
            logger.error("Storage backend is not MongoGridFSStorage. Check STORAGE_BACKEND.")
            return

        base_url = settings.PUBLIC_API_BASE_URL.rstrip("/")
        
        # Find rows missing storage_key or file_token
        media_items = db.query(GeneratedMedia).filter(
            (GeneratedMedia.storage_key == None) | (GeneratedMedia.file_token == None)
        ).all()
        
        logger.info(f"Found {len(media_items)} media items to migrate.")
        
        for media in media_items:
            try:
                original_path_or_url = media.storage_url or getattr(media, "image_path", None)
                if not original_path_or_url:
                    logger.warning(f"Media {media.id} has no storage_url. Skipping.")
                    continue
                    
                data = None
                
                # Try to load file
                if original_path_or_url.startswith("http"):
                    # Check if it's already a GridFS route - shouldn't be if storage_key is missing
                    if "/api/media/" in original_path_or_url and "/file" in original_path_or_url:
                        logger.warning(f"Media {media.id} looks like a new route but has no storage_key. Need manual fix.")
                        continue
                        
                    # It's an external URL or S3 URL
                    try:
                        resp = httpx.get(original_path_or_url, timeout=30)
                        if resp.status_code == 200:
                            data = resp.content
                    except Exception as e:
                        logger.error(f"Failed to download {original_path_or_url} for media {media.id}: {e}")
                else:
                    # It's a local file path
                    # Handle legacy format where it might be relative
                    local_path = original_path_or_url
                    if not os.path.isabs(local_path):
                        local_path = os.path.join(settings.MEDIA_DIR, local_path)
                        
                    if os.path.exists(local_path):
                        with open(local_path, "rb") as fh:
                            data = fh.read()
                    else:
                        logger.error(f"Local file not found: {local_path} for media {media.id}")
                
                if not data:
                    media.generation_status = "FAILED"
                    media.error = "Migration failed: original file not found"
                    db.commit()
                    continue
                    
                # Upload to GridFS
                ext = "jpg" if media.mime_type == "image/jpeg" else "mp4" if media.mime_type == "video/mp4" else "bin"
                filename = f"{media.property_id}_{media.id}.{ext}"
                mime_type = media.mime_type or "application/octet-stream"
                
                file_token = secrets.token_urlsafe(32)
                sha256 = hashlib.sha256(data).hexdigest()
                
                storage_key, size_bytes = storage.upload(
                    data, filename, mime_type, metadata={"media_id": media.id, "property_id": media.property_id}
                )
                
                media.storage_key = storage_key
                media.size_bytes = size_bytes
                media.file_token = file_token
                media.sha256 = sha256
                media.storage_url = f"{base_url}/api/media/{media.id}/file?t={file_token}"
                db.commit()
                
                logger.info(f"Successfully migrated media {media.id}")
                
            except Exception as e:
                logger.error(f"Error migrating media {media.id}: {e}")
                media.generation_status = "FAILED"
                media.error = f"Migration error: {str(e)}"
                db.commit()
                
    finally:
        db.close()

if __name__ == "__main__":
    main()
