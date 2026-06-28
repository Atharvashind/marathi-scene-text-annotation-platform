from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from backend.database import get_db
from backend.models import Image, Annotation
from backend.services.export_service import to_yolo, to_coco, to_label_studio, to_custom_json

router = APIRouter(prefix="/api/export", tags=["export"])

ExportFormat = str  # "yolo" | "coco" | "labelstudio" | "custom_json"


async def _get_pairs_for_image(image_id: int, db: AsyncSession):
    result = await db.execute(select(Image).where(Image.id == image_id))
    image = result.scalar_one_or_none()
    if image is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    ann_result = await db.execute(
        select(Annotation).where(Annotation.image_id == image_id)
    )
    annotations = ann_result.scalars().all()
    return [(image, list(annotations))]


async def _get_pairs_for_project(
    db: AsyncSession, status_filter: Optional[str] = None
):
    query = select(Image)
    if status_filter:
        query = query.where(Image.status == status_filter)
    result = await db.execute(query)
    images = result.scalars().all()

    pairs = []
    for image in images:
        ann_result = await db.execute(
            select(Annotation).where(Annotation.image_id == image.id)
        )
        annotations = ann_result.scalars().all()
        pairs.append((image, list(annotations)))
    return pairs


def _build_response(fmt: str, pairs, is_empty: bool) -> Response:
    headers = {}
    if is_empty:
        headers["X-Empty-Export"] = "true"

    if fmt == "yolo":
        if not pairs:
            content = ""
        else:
            lines = []
            for img, anns in pairs:
                lines.append(to_yolo(img, anns))
            content = "\n".join(lines)
        return Response(content=content, media_type="text/plain", headers=headers)

    elif fmt == "coco":
        data = to_coco(pairs)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers=headers,
        )

    elif fmt == "labelstudio":
        data = to_label_studio(pairs)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers=headers,
        )

    elif fmt == "custom_json":
        data = to_custom_json(pairs)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers=headers,
        )

    else:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Unknown export format '{fmt}'. Use: yolo, coco, labelstudio, custom_json",
        )


@router.get("/{image_id}")
async def export_image(
    image_id: int,
    format: ExportFormat = Query("custom_json"),
    db: AsyncSession = Depends(get_db),
):
    pairs = await _get_pairs_for_image(image_id, db)
    total_anns = sum(len([a for a in anns if not a.is_deleted]) for _, anns in pairs)
    return _build_response(format, pairs, is_empty=(total_anns == 0))


@router.get("/project/all")
async def export_project(
    format: ExportFormat = Query("custom_json"),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    pairs = await _get_pairs_for_project(db, status_filter=status)
    total_anns = sum(len([a for a in anns if not a.is_deleted]) for _, anns in pairs)
    return _build_response(format, pairs, is_empty=(total_anns == 0))
