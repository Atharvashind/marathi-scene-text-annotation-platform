import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.auth.dependencies import get_current_user
from backend.models import User, Image, Project, Annotation
from backend.schemas import AnnotationCreate, AnnotationUpdate, AnnotationResponse
from backend.services.annotation_service import (
    create_annotation, get_annotations, update_annotation, delete_annotation
)

router = APIRouter(tags=["annotations"])


async def _verify_image_ownership(
    image_id: uuid.UUID, project_id: uuid.UUID, user: User, db: AsyncSession
) -> None:
    result = await db.execute(
        select(Image)
        .join(Project, Image.project_id == Project.id)
        .where(Image.id == image_id, Project.id == project_id, Project.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not found")


@router.get("/projects/{project_id}/annotations/{image_id}", response_model=List[AnnotationResponse])
async def list_annotations(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_image_ownership(image_id, project_id, user, db)
    return await get_annotations(image_id, db)


@router.post("/projects/{project_id}/annotations/{image_id}", response_model=AnnotationResponse, status_code=201)
async def create_annotation_endpoint(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    body: AnnotationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_image_ownership(image_id, project_id, user, db)
    return await create_annotation(image_id, body, db, ocr_generated=False)


@router.patch("/projects/{project_id}/annotations/ann/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation_endpoint(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    body: AnnotationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ann_result = await db.execute(
        select(Annotation)
        .join(Image, Annotation.image_id == Image.id)
        .join(Project, Image.project_id == Project.id)
        .where(Annotation.id == annotation_id, Project.user_id == user.id, Annotation.is_deleted == False)
    )
    if ann_result.scalar_one_or_none() is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not found")
    return await update_annotation(annotation_id, body, db)


@router.delete("/projects/{project_id}/annotations/ann/{annotation_id}")
async def delete_annotation_endpoint(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ann_result = await db.execute(
        select(Annotation)
        .join(Image, Annotation.image_id == Image.id)
        .join(Project, Image.project_id == Project.id)
        .where(Annotation.id == annotation_id, Project.user_id == user.id, Annotation.is_deleted == False)
    )
    if ann_result.scalar_one_or_none() is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not found")
    return await delete_annotation(annotation_id, db)
