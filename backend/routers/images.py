from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.schemas import ImageResponse, UploadFileResult, ImageStatusUpdate
from backend.models import Image
from backend.services.image_service import (
    upload_images,
    get_all_images,
    get_image,
    delete_image,
    update_image_status,
)

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("/upload", response_model=List[UploadFileResult])
async def upload_images_endpoint(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    return await upload_images(files, db)


@router.get("", response_model=List[ImageResponse])
async def list_images(db: AsyncSession = Depends(get_db)):
    return await get_all_images(db)


@router.get("/pending-ocr", response_model=List[ImageResponse])
async def list_pending_ocr(db: AsyncSession = Depends(get_db)):
    """Return images that haven't had OCR run yet (status = Uploaded)."""
    result = await db.execute(
        select(Image)
        .where(Image.status == "Uploaded")
        .order_by(Image.upload_date.asc())
    )
    images = result.scalars().all()
    return [ImageResponse.model_validate(img) for img in images]


@router.get("/{image_id}/file")
async def serve_image_file(image_id: int, db: AsyncSession = Depends(get_db)):
    image = await get_image(image_id, db)
    return FileResponse(image.filepath, media_type="image/jpeg")


@router.get("/{image_id}/thumbnail")
async def serve_thumbnail(image_id: int, db: AsyncSession = Depends(get_db)):
    image = await get_image(image_id, db)
    return FileResponse(image.filepath, media_type="image/jpeg")


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image_endpoint(image_id: int, db: AsyncSession = Depends(get_db)):
    image = await get_image(image_id, db)
    return ImageResponse.model_validate(image)


@router.patch("/{image_id}/status", response_model=ImageResponse)
async def update_status(
    image_id: int,
    body: ImageStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    image = await update_image_status(image_id, body.status, db)
    return ImageResponse.model_validate(image)


@router.delete("/{image_id}", status_code=204)
async def delete_image_endpoint(
    image_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete an image, all its annotations, and the file on disk."""
    await delete_image(image_id, db)
