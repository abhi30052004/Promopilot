import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import health, properties, knowledge, llm, auth, settings_router, dashboard, logs, plans, content, agent, feeds, scheduler_router
from .routers.auth import get_current_user
from .database import SessionLocal
from .models import Setting

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "posts_per_day": 3,
    "stories_per_day": 3,
    "languages": ["he", "en"],
    "approval_mode": "manual",
    "platforms_enabled": ["facebook", "instagram", "tiktok", "x", "telegram"],
    "brand_tone": "relaxing",
    "post_slots": ["09:00", "15:00", "19:00"],
    "story_slots": ["11:00", "17:00", "20:00"]
}

def seed_settings():
    db = SessionLocal()
    try:
        for k, v in DEFAULT_SETTINGS.items():
            existing = db.query(Setting).filter(Setting.key == k).first()
            if not existing:
                s = Setting(key=k, value=v)
                db.add(s)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to seed settings: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    from .scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    
    settings = get_settings()
    
    # Ensure MEDIA_DIR exists
    os.makedirs(settings.MEDIA_DIR, exist_ok=True)
    
    # Seed default settings
    seed_settings()
    
    # Startup logging
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
    
    yield
    
    from .scheduler import stop_scheduler
    stop_scheduler()
    logger.info("Shutting down application")

app = FastAPI(lifespan=lifespan)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from urllib.parse import urlparse

os.makedirs(settings.MEDIA_DIR, exist_ok=True)
mount_path = urlparse(settings.MEDIA_BASE_URL).path
if not mount_path.startswith("/"):
    mount_path = "/" + mount_path
app.mount(mount_path, StaticFiles(directory=settings.MEDIA_DIR), name="media")

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
app.include_router(scheduler_router.router, prefix="/api", dependencies=protected_route)
