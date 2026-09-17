import uuid
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.auth.dependencies import get_current_user
from backend.models import User, Image, Project, Annotation
from backend.projects.service import get_project_for_user
from backend.services.export_service import to_yolo, to_coco, to_label_studio, to_custom_json

router = APIRouter(tags=["export"])


async def _get_project_pairs(
    project_id: uuid.UUID, user: User, db: AsyncSession, status_filter: Optional[str] = None
):
    await get_project_for_user(project_id, user, db)
    q = select(Image).where(Image.project_id == project_id)
    if status_filter:
        q = q.where(Image.status == status_filter)
    images_result = await db.execute(q)
    images = images_result.scalars().all()
    pairs = []
    for img in images:
        anns_result = await db.execute(
            select(Annotation).where(Annotation.image_id == img.id)
        )
        pairs.append((img, list(anns_result.scalars().all())))
    return pairs


def _build_response(fmt: str, pairs) -> Response:
    total = sum(len([a for a in anns if not a.is_deleted]) for _, anns in pairs)
    headers = {"X-Empty-Export": "true"} if total == 0 else {}
    if fmt == "yolo":
        content = "\n".join(to_yolo(img, anns) for img, anns in pairs) if pairs else ""
        return Response(content=content, media_type="text/plain", headers=headers)
    elif fmt == "coco":
        return Response(content=json.dumps(to_coco(pairs), indent=2),
                        media_type="application/json", headers=headers)
    elif fmt == "labelstudio":
        return Response(content=json.dumps(to_label_studio(pairs), indent=2),
                        media_type="application/json", headers=headers)
    else:
        return Response(content=json.dumps(to_custom_json(pairs), indent=2),
                        media_type="application/json", headers=headers)


@router.get("/projects/{project_id}/export/all")
async def export_project(
    project_id: uuid.UUID,
    format: str = Query("custom_json"),
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pairs = await _get_project_pairs(project_id, user, db, status_filter=status)
    return _build_response(format, pairs)


@router.get("/projects/{project_id}/export/{image_id}")
async def export_image(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    format: str = Query("custom_json"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Image)
        .join(Project, Image.project_id == Project.id)
        .where(Image.id == image_id, Project.id == project_id, Project.user_id == user.id)
    )
    image = result.scalar_one_or_none()
    if image is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not found")
    anns_result = await db.execute(select(Annotation).where(Annotation.image_id == image_id))
    pairs = [(image, list(anns_result.scalars().all()))]
    return _build_response(format, pairs)
