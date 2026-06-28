from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import AnnotationResponse
from backend.services.ocr_service import run_ocr

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/{image_id}", response_model=List[AnnotationResponse])
async def trigger_ocr(image_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger OCR on an image. Returns the created annotations."""
    return await run_ocr(image_id, db)
