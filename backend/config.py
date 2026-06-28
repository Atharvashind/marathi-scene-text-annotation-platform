import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Image storage
IMAGES_DIR: Path = Path(os.getenv("IMAGES_DIR", str(BASE_DIR / "images")))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'annotations.db'}")

# Upload limits
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))

# OCR engine selection
ACTIVE_OCR_ENGINE: str = os.getenv("ACTIVE_OCR_ENGINE", "indic_photo_ocr")
