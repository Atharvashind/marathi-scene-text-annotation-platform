from typing import List, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models import Annotation, Image
from backend.schemas import AnnotationCreate, AnnotationUpdate, AnnotationResponse


async def _guard_approved(image_id: int, db: AsyncSession) -> None:
    """Raise HTTP 403 if the parent image is Approved."""
    result = await db.execute(select(Image).where(Image.id == image_id))
    image: Image | None = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    if image.status == "Approved":
        raise HTTPException(
            status_code=403,
            detail="Cannot modify annotations on an Approved image. Re-open the image first.",
        )


async def create_annotation(
    image_id: int, data: AnnotationCreate, db: AsyncSession, ocr_generated: bool = False,
    confidence: float = 1.0
) -> AnnotationResponse:
    await _guard_approved(image_id, db)

    ann = Annotation(
        image_id=image_id,
        x1=data.x1,
        y1=data.y1,
        x2=data.x2,
        y2=data.y2,
        text=data.text,
        label=data.label,
        confidence=confidence if ocr_generated else 1.0,
        accepted=not ocr_generated,   # manual = accepted, OCR = pending review
        ocr_generated=ocr_generated,
        is_corrected=False,
        is_deleted=False,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return AnnotationResponse.model_validate(ann)


async def get_annotations(image_id: int, db: AsyncSession) -> List[AnnotationResponse]:
    result = await db.execute(
        select(Annotation)
        .where(Annotation.image_id == image_id, Annotation.is_deleted == False)
        .order_by(Annotation.id)
    )
    annotations = result.scalars().all()
    return [AnnotationResponse.model_validate(a) for a in annotations]


async def update_annotation(
    annotation_id: int, data: AnnotationUpdate, db: AsyncSession
) -> AnnotationResponse:
    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id, Annotation.is_deleted == False)
    )
    ann: Annotation | None = result.scalar_one_or_none()
    if ann is None:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} not found")

    await _guard_approved(ann.image_id, db)

    # Track corrections on OCR-generated annotations
    if ann.ocr_generated:
        if data.text is not None and data.text != ann.text:
            ann.is_corrected = True
        if data.label is not None and data.label != ann.label:
            ann.is_corrected = True

    if data.text is not None:
        ann.text = data.text
    if data.label is not None:
        ann.label = data.label
    if data.accepted is not None:
        ann.accepted = data.accepted
    # Bounding box coordinate updates (drag / resize from canvas)
    if data.x1 is not None:
        ann.x1 = data.x1
    if data.y1 is not None:
        ann.y1 = data.y1
    if data.x2 is not None:
        ann.x2 = data.x2
    if data.y2 is not None:
        ann.y2 = data.y2

    ann.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(ann)
    return AnnotationResponse.model_validate(ann)


async def delete_annotation(annotation_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id, Annotation.is_deleted == False)
    )
    ann: Annotation | None = result.scalar_one_or_none()
    if ann is None:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} not found")

    await _guard_approved(ann.image_id, db)

    ann.is_deleted = True
    ann.updated_at = datetime.utcnow()
    await db.commit()
    return {"deleted": True, "id": annotation_id}
