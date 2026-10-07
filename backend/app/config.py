from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_MODEL: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    IMAGE_MODEL: Optional[str] = None
    OPENAI_EMBEDDING_MODEL: Optional[str] = None
    CHROMA_PATH: Optional[str] = None
    ENABLE_VECTOR_INDEXING: bool = False
    MEDIA_DIR: str = "media"
    MEDIA_BASE_URL: str = "/media"
    TIMEZONE: str = "Asia/Jerusalem"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    ADMIN_USERNAME: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    JWT_SECRET: Optional[str] = None
    APP_ENV: str = "development"

    # Storage backend. Local is for development only; use s3 or mongo on Render.
    STORAGE_BACKEND: str = "local"   # local | s3 | mongo
    MONGODB_URI: Optional[str] = None
    MONGODB_DB: str = "promopilot_media"
    S3_BUCKET: Optional[str] = None
    S3_REGION: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None
    S3_PREFIX: str = "promopilot"
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    MEDIA_MAX_TOTAL_MB: int = 400

    # Media limits
    MAX_AI_IMAGES_PER_PROPERTY: int = 3

    # Scheduler tick token
    SCHEDULER_TOKEN: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
