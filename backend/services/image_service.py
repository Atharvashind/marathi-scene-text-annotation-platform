import io
import os
import shutil
from pathlib import Path
from typing import List, Tuple
import magic
from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile, HTTPException

from backend.config import IMAGES_DIR, MAX_FILE_SIZE_MB
from backend.models import Image
from backend.schemas import UploadFileResult, ImageResponse

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Allowed state transitions
VALID_TRANSITIONS = {
    "Uploaded": {"OCR_Completed", "Under_Review"},
    "OCR_Completed": {"Under_Review"},
    "Under_Review": {"Approved", "OCR_Completed"},
    "Approved": {"Under_Review"},
}


def validate_mime_type(data: bytes) -> Tuple[bool, str]:
    """Return (is_valid, mime_type) for the given file bytes."""
    mime = magic.from_buffer(data, mime=True)
    return mime in ALLOWED_MIME_TYPES, mime


async def upload_images(
    files: List[UploadFile], db: AsyncSession
) -> List[UploadFileResult]:
    results: List[UploadFileResult] = []

    for file in files:
        try:
            # Read file bytes
            data = await file.read()

            # Check file size
            max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
            if len(data) > max_bytes:
                results.append(UploadFileResult(
                    filename=file.filename or "unknown",
                    success=False,
                    error=f"File exceeds maximum size of {MAX_FILE_SIZE_MB} MB",
                ))
                continue

            # Validate MIME type
            is_valid, mime_type = validate_mime_type(data)
            if not is_valid:
                results.append(UploadFileResult(
                    filename=file.filename or "unknown",
                    success=False,
                    error=f"Unsupported file type '{mime_type}'. Accepted: image/jpeg, image/png, image/webp",
                ))
                continue

            # Read image dimensions
            with PILImage.open(io.BytesIO(data)) as img:
                width, height = img.size

            # Save to IMAGES_DIR
            safe_name = Path(file.filename).name if file.filename else "image"
            dest_path = IMAGES_DIR / safe_name
            # Avoid collisions
            counter = 1
            while dest_path.exists():
                stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                dest_path = IMAGES_DIR / f"{stem}_{counter}{suffix}"
                counter += 1

            with open(dest_path, "wb") as f:
                f.write(data)

            # Persist DB record
            image = Image(
                filename=safe_name,
                filepath=str(dest_path),
                width=width,
                height=height,
                status="Uploaded",
            )
            db.add(image)
            await db.commit()
            await db.refresh(image)

            results.append(UploadFileResult(
                filename=file.filename or safe_name,
                success=True,
                image=ImageResponse.model_validate(image),
            ))

        except Exception as exc:
            await db.rollback()
            results.append(UploadFileResult(
                filename=file.filename or "unknown",
                success=False,
                error=str(exc),
            ))

    return results


async def get_all_images(db: AsyncSession) -> List[ImageResponse]:
    result = await db.execute(select(Image).order_by(Image.upload_date.desc()))
    images = result.scalars().all()
    return [ImageResponse.model_validate(img) for img in images]


async def get_image(image_id: int, db: AsyncSession) -> Image:
    result = await db.execute(select(Image).where(Image.id == image_id))
    image = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    return image


async def update_image_status(
    image_id: int, new_status: str, db: AsyncSession
) -> Image:
    image = await get_image(image_id, db)
    allowed = VALID_TRANSITIONS.get(image.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from '{image.status}' to '{new_status}'. "
                   f"Allowed transitions: {sorted(allowed)}",
        )
    image.status = new_status
    if new_status == "Approved":
        from datetime import datetime
        image.approved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(image)

    # Publish SSE events to connected clients
    from backend.routers.events import publish_event
    publish_event("status_changed", {"image_id": image_id, "status": new_status})
    if new_status == "Approved":
        publish_event("image_approved", {"image_id": image_id})

    return image
