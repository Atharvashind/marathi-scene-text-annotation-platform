import os
from pathlib import Path
from functools import lru_cache

from backend.storage.base import BaseStorageProvider


@lru_cache(maxsize=1)
def get_storage_provider() -> BaseStorageProvider:
    """
    Resolve and return the active storage provider singleton.
    Controlled by the IMAGE_STORAGE environment variable:
      - "local" (default) → LocalDiskProvider
      - "s3"              → S3Provider (not yet implemented)
    """
    provider_name = os.environ.get("IMAGE_STORAGE", "local").lower()

    if provider_name == "local":
        from backend.storage.local import LocalDiskProvider
        images_dir = Path(os.environ.get("IMAGES_DIR", "backend/images"))
        images_dir.mkdir(parents=True, exist_ok=True)
        return LocalDiskProvider(base_dir=images_dir)

    elif provider_name == "s3":
        from backend.storage.s3 import S3Provider
        return S3Provider(
            bucket=os.environ["S3_BUCKET"],
            region=os.environ["S3_REGION"],
            access_key=os.environ["S3_ACCESS_KEY"],
            secret_key=os.environ["S3_SECRET_KEY"],
        )

    raise ValueError(f"Unknown IMAGE_STORAGE provider: '{provider_name}'. Supported: local, s3")
