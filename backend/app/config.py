from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_EMBEDDING_MODEL: Optional[str] = None
    CHROMA_PATH: Optional[str] = None
    MEDIA_DIR: str = "media"
    MEDIA_BASE_URL: str = "/media"
    TIMEZONE: str = "Asia/Jerusalem"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    ADMIN_USERNAME: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    JWT_SECRET: Optional[str] = None
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
