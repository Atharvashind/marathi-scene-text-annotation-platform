from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import ImageResponse, UploadFileResult, ImageStatusUpdate
from backend.services.image_service import (
    upload_images,
    get_all_images,
    get_image,
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


@router.get("/{image_id}/file")
async def serve_image_file(image_id: int, db: AsyncSession = Depends(get_db)):
    """Serve the raw image file for display in the canvas."""
    image = await get_image(image_id, db)
    return FileResponse(image.filepath, media_type="image/jpeg")


@router.get("/{image_id}/thumbnail")
async def serve_thumbnail(image_id: int, db: AsyncSession = Depends(get_db)):
    """Serve the image as a thumbnail (same file, browser scales it)."""
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
