import uuid
from typing import List

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db, AsyncSessionLocal
from backend.auth.dependencies import get_current_user
from backend.models import User, Image, Project
from backend.schemas import AnnotationResponse
from backend.services.ocr_service import run_ocr

router = APIRouter(tags=["ocr"])


# ── Ownership helper ───────────────────────────────────────────────────────────

async def _verify_image_ownership(
    image_id: uuid.UUID, project_id: uuid.UUID, user: User, db: AsyncSession
) -> Image:
    result = await db.execute(
        select(Image)
        .join(Project, Image.project_id == Project.id)
        .where(Image.id == image_id, Project.id == project_id, Project.user_id == user.id)
    )
    image = result.scalar_one_or_none()
    if image is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not found")
    return image


# ── IndicPhotoOCR endpoints (default) ─────────────────────────────────────────

@router.post("/projects/{project_id}/ocr/{image_id}", response_model=List[AnnotationResponse])
async def trigger_ocr(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run IndicPhotoOCR (stock model) on a single image."""
    await _verify_image_ownership(image_id, project_id, user, db)
    return await run_ocr(image_id, db, engine="indic_photo_ocr")


@router.post("/projects/{project_id}/ocr/batch/all")
async def trigger_batch_ocr(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch IndicPhotoOCR (stock model) on all uploaded images in the project."""
    result = await db.execute(
        select(Image.id)
        .join(Project, Image.project_id == Project.id)
        .where(Project.id == project_id, Project.user_id == user.id, Image.status == "Uploaded")
    )
    image_ids = [row[0] for row in result.fetchall()]
    if not image_ids:
        return {"queued": 0, "message": "No images pending OCR"}
    background_tasks.add_task(_run_batch_ocr, image_ids, "indic_photo_ocr")
    return {"queued": len(image_ids), "message": f"OCR queued for {len(image_ids)} images"}


# ── Finetuned-model endpoints ─────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/ocr/finetuned/{image_id}",
    response_model=List[AnnotationResponse],
)
async def trigger_finetuned_ocr(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run our finetuned Marathi recogniser on a single image."""
    await _verify_image_ownership(image_id, project_id, user, db)
    return await run_ocr(image_id, db, engine="finetuned")


@router.post("/projects/{project_id}/ocr/finetuned/batch/all")
async def trigger_finetuned_batch_ocr(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch finetuned OCR on all uploaded images in the project."""
    result = await db.execute(
        select(Image.id)
        .join(Project, Image.project_id == Project.id)
        .where(Project.id == project_id, Project.user_id == user.id, Image.status == "Uploaded")
    )
    image_ids = [row[0] for row in result.fetchall()]
    if not image_ids:
        return {"queued": 0, "message": "No images pending OCR"}
    background_tasks.add_task(_run_batch_ocr, image_ids, "finetuned")
    return {"queued": len(image_ids), "message": f"Finetuned OCR queued for {len(image_ids)} images"}


# ── Shared background task ─────────────────────────────────────────────────────

async def _run_batch_ocr(image_ids: list, engine: str) -> None:
    from backend.routers.events import publish_event
    total = len(image_ids)
    completed = 0
    failed = 0
    publish_event("batch_ocr_started", {"total": total, "engine": engine})
    for image_id in image_ids:
        try:
            async with AsyncSessionLocal() as db:
                await run_ocr(image_id, db, engine=engine)
            completed += 1
        except Exception as exc:
            failed += 1
            publish_event("batch_ocr_image_failed", {
                "image_id": str(image_id), "error": str(exc),
                "completed": completed, "failed": failed, "total": total,
            })
            continue
        publish_event("batch_ocr_progress", {
            "image_id": str(image_id), "completed": completed,
            "failed": failed, "total": total,
        })
    publish_event("batch_ocr_finished", {
        "completed": completed, "failed": failed, "total": total,
    })
