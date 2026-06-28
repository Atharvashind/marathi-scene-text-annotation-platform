from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import AnnotationCreate, AnnotationUpdate, AnnotationResponse
from backend.services.annotation_service import (
    create_annotation,
    get_annotations,
    update_annotation,
    delete_annotation,
)

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


@router.get("/{image_id}", response_model=List[AnnotationResponse])
async def list_annotations(image_id: int, db: AsyncSession = Depends(get_db)):
    return await get_annotations(image_id, db)


@router.post("/{image_id}", response_model=AnnotationResponse, status_code=201)
async def create_annotation_endpoint(
    image_id: int,
    body: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_annotation(image_id, body, db, ocr_generated=False)


@router.patch("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation_endpoint(
    annotation_id: int,
    body: AnnotationUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_annotation(annotation_id, body, db)


@router.delete("/{annotation_id}")
async def delete_annotation_endpoint(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await delete_annotation(annotation_id, db)
