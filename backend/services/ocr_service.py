import asyncio
from typing import Sequence, List

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import ACTIVE_OCR_ENGINE
from backend.ocr.base import BaseOCRAdapter, OCRResult
from backend.models import Image, Annotation
from backend.schemas import AnnotationResponse

OCR_TIMEOUT_SECONDS = 60


def get_ocr_adapter() -> BaseOCRAdapter:
    """Resolve the active OCR adapter from config."""
    engine = ACTIVE_OCR_ENGINE.lower()
    if engine == "indic_photo_ocr":
        from backend.ocr.indic_photo_ocr import IndicPhotoOCRAdapter
        return IndicPhotoOCRAdapter()
    elif engine == "easyocr":
        raise NotImplementedError("EasyOCR adapter is not yet implemented")
    elif engine == "paddleocr":
        raise NotImplementedError("PaddleOCR adapter is not yet implemented")
    else:
        raise ValueError(f"Unknown OCR engine: {engine}")


async def run_ocr(image_id: int, db: AsyncSession) -> List[AnnotationResponse]:
    """
    Run OCR on the given image.
    - Validates image status (must be Uploaded or Under_Review)
    - Enforces 60 s timeout
    - Persists annotations and advances image status to OCR_Completed
    - Leaves image status unchanged on any failure
    """
    from sqlalchemy import select
    result = await db.execute(select(Image).where(Image.id == image_id))
    image: Image | None = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")

    if image.status not in ("Uploaded", "Under_Review"):
        raise HTTPException(
            status_code=409,
            detail=f"OCR can only run on images with status 'Uploaded' or 'Under_Review'. "
                   f"Current status: '{image.status}'",
        )

    adapter = get_ocr_adapter()

    try:
        ocr_results: Sequence[OCRResult] = await asyncio.wait_for(
            adapter.run(image.filepath),
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"OCR timed out after {OCR_TIMEOUT_SECONDS} seconds",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OCR engine error: {exc}",
        )

    # Bulk-insert annotation rows — use auto-detected label from OCR
    VALID_LABELS = {"Marathi", "English", "Numeric", "Mixed", "Logo"}
    annotations: list[Annotation] = []
    for r in ocr_results:
        label = r.label if r.label in VALID_LABELS else "Marathi"
        ann = Annotation(
            image_id=image_id,
            x1=r.x1,
            y1=r.y1,
            x2=r.x2,
            y2=r.y2,
            text=r.text,
            label=label,
            confidence=r.confidence,
            accepted=False,
            ocr_generated=True,
        )
        db.add(ann)
        annotations.append(ann)

    # Advance status
    image.status = "OCR_Completed"
    await db.commit()

    for ann in annotations:
        await db.refresh(ann)

    # Publish SSE event to connected clients
    from backend.routers.events import publish_event
    publish_event("ocr_completed", {"image_id": image_id, "annotation_count": len(annotations)})

    return [AnnotationResponse.model_validate(ann) for ann in annotations]
