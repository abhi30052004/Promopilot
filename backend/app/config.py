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
    OPENAI_IMAGE_QUALITY: str = "low"   # low = fastest/cheapest; medium|high are slower
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
    MONGODB_DATABASE: Optional[str] = None   # alias of MONGODB_DB (spec name)
    S3_BUCKET: Optional[str] = None
    S3_REGION: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None
    S3_PREFIX: str = "promopilot"
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    MEDIA_MAX_TOTAL_MB: int = 400

    # Media limits
    MAX_AI_IMAGES_PER_PROPERTY: int = 3

    # Workflow defaults (persisted values in the settings table win over these)
    DEFAULT_CONTACT_EMAIL: str = "contact@tzelahahar.co.il"
    DEFAULT_LANGUAGE: str = "en"
    DEFAULT_APPROVAL_MODE: str = "human"
    DEFAULT_PLATFORMS: str = "instagram,facebook,linkedin"
    FRONTEND_URL: Optional[str] = None
    # Automation safety valve: max properties auto-processed (AI + media cost) per run.
    AUTOMATION_BATCH_LIMIT: int = 3

    # Scheduler tick token
    SCHEDULER_TOKEN: Optional[str] = None

    @property
    def mongo_db_name(self) -> str:
        return self.MONGODB_DATABASE or self.MONGODB_DB

    @property
    def default_platforms(self) -> list:
        return [p.strip().lower() for p in self.DEFAULT_PLATFORMS.split(",") if p.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
