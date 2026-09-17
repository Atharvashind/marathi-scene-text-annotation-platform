from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import Image, Annotation
from backend.schemas import MetricsResponse, ProjectMetricsResponse
from backend.services.metrics_service import compute_image_metrics, compute_project_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/project", response_model=ProjectMetricsResponse)
async def get_project_metrics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Image))
    images = result.scalars().all()

    pairs = []
    for image in images:
        ann_result = await db.execute(
            select(Annotation).where(Annotation.image_id == image.id)
        )
        annotations = ann_result.scalars().all()
        pairs.append((image.id, annotations))

    metrics = compute_project_metrics(pairs)
    return ProjectMetricsResponse(**metrics)


@router.get("/{image_id}", response_model=MetricsResponse)
async def get_image_metrics(image_id: int, db: AsyncSession = Depends(get_db)):
    ann_result = await db.execute(
        select(Annotation).where(Annotation.image_id == image_id)
    )
    annotations = ann_result.scalars().all()
    metrics = compute_image_metrics(annotations)
    return MetricsResponse(image_id=image_id, **metrics)
