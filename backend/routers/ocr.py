from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db, AsyncSessionLocal
from backend.models import Image
from backend.schemas import AnnotationResponse
from backend.services.ocr_service import run_ocr
from backend.routers.events import publish_event

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/{image_id}", response_model=List[AnnotationResponse])
async def trigger_ocr(image_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger OCR on a single image. Returns the created annotations."""
    return await run_ocr(image_id, db)


@router.post("/batch/all")
async def trigger_batch_ocr(background_tasks: BackgroundTasks):
    """
    Queue OCR for all images with status 'Uploaded'.
    Runs in the background — progress is streamed via SSE events.
    Returns immediately with the count of queued images.
    """
    # Fetch image IDs to process
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Image.id).where(Image.status == "Uploaded").order_by(Image.upload_date.asc())
        )
        image_ids = [row[0] for row in result.fetchall()]

    if not image_ids:
        return {"queued": 0, "message": "No images with status 'Uploaded' found"}

    background_tasks.add_task(_run_batch_ocr, image_ids)
    return {"queued": len(image_ids), "message": f"OCR queued for {len(image_ids)} images"}


async def _run_batch_ocr(image_ids: list[int]) -> None:
    """Background task: run OCR on each image sequentially, publishing SSE progress."""
    total = len(image_ids)
    completed = 0
    failed = 0

    publish_event("batch_ocr_started", {"total": total})

    for image_id in image_ids:
        try:
            async with AsyncSessionLocal() as db:
                await run_ocr(image_id, db)
            completed += 1
        except Exception as exc:
            failed += 1
            publish_event("batch_ocr_image_failed", {
                "image_id": image_id,
                "error": str(exc),
                "completed": completed,
                "failed": failed,
                "total": total,
            })
            continue

        publish_event("batch_ocr_progress", {
            "image_id": image_id,
            "completed": completed,
            "failed": failed,
            "total": total,
        })

    publish_event("batch_ocr_finished", {
        "completed": completed,
        "failed": failed,
        "total": total,
    })
