import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import (
    health, properties, knowledge, llm, auth, settings_router,
    dashboard, logs, plans, content, agent, feeds, scheduler_router, calendar
)
from .routers.auth import get_current_user
from .database import SessionLocal
from .models import Setting

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_cfg = get_settings()
DEFAULT_SETTINGS = {
    "posts_per_day": 3,
    "stories_per_day": 3,
    "story_duration_seconds": 10,
    "max_ai_images_per_property": 3,
    "languages": ["en", "he"],
    "default_language": getattr(_cfg, "DEFAULT_LANGUAGE", "en") if getattr(_cfg, "DEFAULT_LANGUAGE", "en") in ("en", "he") else "en",
    "contact_email": getattr(_cfg, "DEFAULT_CONTACT_EMAIL", "contact@tzelahahar.co.il"),
    "approval_mode": "AUTOMATION" if str(getattr(_cfg, "DEFAULT_APPROVAL_MODE", "human")).lower().startswith("auto") else "HUMAN",
    "platforms_enabled": getattr(_cfg, "default_platforms", ["instagram", "facebook", "linkedin"]),
    "brand_tone": "relaxing",
    "post_slots": ["09:00", "15:00", "19:00"],
    "story_slots": ["11:00", "17:00", "20:00"],
}


def seed_settings():
    db = SessionLocal()
    try:
        for k, v in DEFAULT_SETTINGS.items():
            existing = db.query(Setting).filter(Setting.key == k).first()
            if not existing:
                s = Setting(key=k, value=v)
                db.add(s)
            else:
                # Migrate old values: manual -> HUMAN, auto -> AUTOMATION
                if k == "approval_mode":
                    if existing.value in ("manual", "manual_approval"):
                        existing.value = "HUMAN"
                    elif existing.value in ("auto", "automatic"):
                        existing.value = "AUTOMATION"
                # Replace the pre-spec platform default with the spec default (Instagram/Facebook/LinkedIn).
                if k == "platforms_enabled" and existing.value == ["facebook", "instagram", "tiktok", "x", "telegram"]:
                    existing.value = v
        db.commit()
    except Exception as e:
        logger.error(f"Failed to seed settings: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.APP_ENV.lower() == "production":
        if settings.STORAGE_BACKEND.lower() == "local":
            raise RuntimeError(
                "Production requires persistent media storage: set STORAGE_BACKEND=s3 or mongo"
            )
        if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD or not settings.JWT_SECRET:
            raise RuntimeError("ADMIN_USERNAME, ADMIN_PASSWORD, and JWT_SECRET are required in production")
        if not settings.SCHEDULER_TOKEN:
            raise RuntimeError("SCHEDULER_TOKEN is required in production")
        if "localhost" in settings.PUBLIC_API_BASE_URL or "127.0.0.1" in settings.PUBLIC_API_BASE_URL:
            raise RuntimeError("PUBLIC_API_BASE_URL must be the public backend URL in production")
        # Fail at startup rather than after an expensive generation job.
        from .services.media_storage import get_storage

        get_storage()
    if settings.STORAGE_BACKEND.lower() == "local":
        os.makedirs(settings.MEDIA_DIR, exist_ok=True)
    seed_settings()

    # Open a few DB connections up-front (a new remote connection costs ~4s).
    def _warm_pool():
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import text
        from .database import engine

        def one(_):
            with engine.connect() as conn:
                conn.execute(text("select 1"))

        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(one, range(4)))
        except Exception as exc:
            logger.warning(f"DB warm-up failed: {exc}")

    import threading as _t
    _t.Thread(target=_warm_pool, daemon=True).start()

    # Store scraped images in GridFS in the background so cards show real images.
    import threading
    from .services.image_validator import store_missing_images

    threading.Thread(target=store_missing_images, daemon=True).start()

    from .scheduler import start_scheduler, stop_scheduler
    start_scheduler()

    # Re-index ChromaDB if collection is empty/missing but properties exist
    try:
        from .services.vectorstore import ensure_index
        ensure_index()
    except Exception as e:
        logger.warning(f"ChromaDB ensure_index failed: {e}")

    db_url = settings.DATABASE_URL
    if "@" in db_url:
        db_host_part = db_url.split("@")[-1]
        db_host = db_host_part.split("/")[0]
    elif "://" in db_url:
        db_host = db_url.split("://")[-1]
    else:
        db_host = db_url

    logger.info(f"Starting application in '{settings.APP_ENV}' environment")
    logger.info(f"Database host: {db_host}")
    logger.info(f"Storage backend: {settings.STORAGE_BACKEND}")

    yield

    from .scheduler import stop_scheduler
    stop_scheduler()
    logger.info("Shutting down application")


app = FastAPI(lifespan=lifespan, title="PromoPilot API", version="2.0.0")

settings = get_settings()

frontend_url = getattr(settings, "FRONTEND_URL", None) or os.getenv("FRONTEND_URL")
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if frontend_url:
    origins.append(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from urllib.parse import urlparse

if settings.STORAGE_BACKEND.lower() == "local":
    os.makedirs(settings.MEDIA_DIR, exist_ok=True)
    mount_path = urlparse(settings.MEDIA_BASE_URL).path
    if not mount_path.startswith("/"):
        mount_path = "/" + mount_path
    app.mount(mount_path, StaticFiles(directory=settings.MEDIA_DIR), name="media")

# Import media router
from .routers import media as media_router

# Include routers
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")

protected_route = [Depends(get_current_user)]
app.include_router(properties.router, prefix="/api", dependencies=protected_route)
app.include_router(knowledge.router, prefix="/api", dependencies=protected_route)
app.include_router(llm.router, prefix="/api", dependencies=protected_route)
app.include_router(settings_router.router, prefix="/api", dependencies=protected_route)
app.include_router(dashboard.router, prefix="/api", dependencies=protected_route)
app.include_router(logs.router, prefix="/api", dependencies=protected_route)
app.include_router(plans.router, prefix="/api", dependencies=protected_route)
app.include_router(content.router, prefix="/api", dependencies=protected_route)
app.include_router(agent.router, prefix="/api", dependencies=protected_route)
app.include_router(feeds.router, prefix="/api", dependencies=protected_route)
app.include_router(calendar.router, prefix="/api", dependencies=protected_route)
app.include_router(scheduler_router.router, prefix="/api", dependencies=protected_route)
app.include_router(media_router.router, prefix="/api", dependencies=protected_route)
# Tokenized media files must be reachable by native <img>/<video> elements, which
# cannot attach the dashboard Authorization header.
app.include_router(media_router.public_router, prefix="/api")
app.include_router(scheduler_router.public_router, prefix="/api")
