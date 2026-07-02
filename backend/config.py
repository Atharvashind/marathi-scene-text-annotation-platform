import os
import sys
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required — exit if missing
    DATABASE_URL: str
    JWT_SECRET: str
    NEXTAUTH_SECRET: str

    # Optional with defaults
    CORS_ORIGIN: str = "http://localhost:3000"
    IMAGE_STORAGE: str = "local"
    IMAGES_DIR: Path = Path("backend/images")
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7
    MAX_FILE_SIZE_MB: int = 20
    ACTIVE_OCR_ENGINE: str = "indic_photo_ocr"
    OCR_BATCH_SIZE: int = 8
    ANALYTICS_PROVIDER: str = "internal"

    @field_validator("DATABASE_URL", "JWT_SECRET", "NEXTAUTH_SECRET", mode="before")
    @classmethod
    def must_not_be_empty(cls, v, info):
        if not v or not str(v).strip():
            print(f"ERROR: Required environment variable '{info.field_name}' is missing or empty.", file=sys.stderr)
            sys.exit(1)
        return v


def _load_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        # pydantic-settings will raise if a required field is missing
        print(f"ERROR: Configuration error — {e}", file=sys.stderr)
        sys.exit(1)


settings = _load_settings()

# Keep these module-level aliases for backward compatibility with existing code
DATABASE_URL = settings.DATABASE_URL
IMAGES_DIR = settings.IMAGES_DIR
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE_MB = settings.MAX_FILE_SIZE_MB
ACTIVE_OCR_ENGINE = settings.ACTIVE_OCR_ENGINE
