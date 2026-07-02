import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.auth.dependencies import get_current_user
from backend.models import User, Image, Project, Annotation
from backend.schemas import MetricsResponse, ProjectMetricsResponse
from backend.services.metrics_service import compute_image_metrics, compute_project_metrics
from backend.projects.service import get_project_for_user

router = APIRouter(tags=["metrics"])


@router.get("/projects/{project_id}/metrics/project", response_model=ProjectMetricsResponse)
async def get_project_metrics(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_for_user(project_id, user, db)
    images_result = await db.execute(select(Image).where(Image.project_id == project_id))
    images = images_result.scalars().all()
    pairs = []
    for img in images:
        anns_result = await db.execute(select(Annotation).where(Annotation.image_id == img.id))
        pairs.append((img.id, anns_result.scalars().all()))
    metrics = compute_project_metrics(pairs)
    return ProjectMetricsResponse(**metrics)


@router.get("/projects/{project_id}/metrics/{image_id}", response_model=MetricsResponse)
async def get_image_metrics(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    img_result = await db.execute(
        select(Image)
        .join(Project, Image.project_id == Project.id)
        .where(Image.id == image_id, Project.id == project_id, Project.user_id == user.id)
    )
    if img_result.scalar_one_or_none() is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not found")
    anns_result = await db.execute(select(Annotation).where(Annotation.image_id == image_id))
    annotations = anns_result.scalars().all()
    metrics = compute_image_metrics(annotations)
    return MetricsResponse(image_id=image_id, **metrics)
