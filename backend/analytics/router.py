import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.database import get_db
from backend.auth.dependencies import get_current_user, require_researcher
from backend.models import User, AnalyticsEvent, OcrAnalytics, AnnotationSession, Project, Image

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def analytics_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects_result = await db.execute(select(func.count(Project.id)).where(Project.user_id == user.id))
    project_count = projects_result.scalar() or 0

    events_result = await db.execute(
        select(func.count(AnalyticsEvent.event_id)).where(AnalyticsEvent.user_id == user.id)
    )
    event_count = events_result.scalar() or 0

    sessions_result = await db.execute(
        select(func.count(AnnotationSession.session_id)).where(
            AnnotationSession.user_id == user.id,
            AnnotationSession.end_time.isnot(None),
        )
    )
    session_count = sessions_result.scalar() or 0

    return {
        "user_id": str(user.id),
        "project_count": project_count,
        "total_events": event_count,
        "completed_sessions": session_count,
    }


@router.get("/user")
async def user_analytics(
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalyticsEvent)
        .where(AnalyticsEvent.user_id == user.id)
        .order_by(AnalyticsEvent.timestamp.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        {
            "event_id": str(e.event_id),
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "duration_ms": e.duration_ms,
        }
        for e in events
    ]


@router.get("/ocr")
async def ocr_analytics(
    project_id: Optional[uuid.UUID] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(OcrAnalytics)
        .join(AnalyticsEvent, OcrAnalytics.event_id == AnalyticsEvent.event_id)
        .where(AnalyticsEvent.user_id == user.id)
    )
    if project_id:
        q = q.where(AnalyticsEvent.project_id == project_id)
    result = await db.execute(q.order_by(AnalyticsEvent.timestamp.desc()).limit(100))
    rows = result.scalars().all()
    return [
        {
            "image_id": str(r.image_id) if r.image_id else None,
            "number_of_boxes": r.number_of_boxes,
            "average_confidence": r.average_confidence,
            "processing_time": r.processing_time,
            "difficulty_score": r.difficulty_score,
            "failure_reason": r.failure_reason,
            "language": r.language,
        }
        for r in rows
    ]


@router.get("/productivity")
async def productivity_metrics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnnotationSession).where(
            AnnotationSession.user_id == user.id,
            AnnotationSession.end_time.isnot(None),
        )
    )
    sessions = result.scalars().all()
    if not sessions:
        return {"message": "No completed sessions yet"}

    total_duration = sum(s.duration or 0 for s in sessions)
    total_created = sum(s.annotations_created for s in sessions)
    total_corrected = sum(s.annotations_corrected for s in sessions)
    count = len(sessions)

    avg_duration = total_duration / count if count else 0
    boxes_per_min = (total_created / (total_duration / 60)) if total_duration > 0 else 0
    correction_pct = (total_corrected / total_created * 100) if total_created > 0 else 0

    return {
        "session_count": count,
        "avg_annotation_time_seconds": round(avg_duration, 1),
        "boxes_per_minute": round(boxes_per_min, 2),
        "correction_percentage": round(correction_pct, 1),
        "total_annotations_created": total_created,
    }


@router.get("/research")
async def research_dashboard(
    user: User = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_projects = (await db.execute(select(func.count(Project.id)))).scalar() or 0
    total_events = (await db.execute(select(func.count(AnalyticsEvent.event_id)))).scalar() or 0

    failure_result = await db.execute(
        select(OcrAnalytics.failure_reason, func.count(OcrAnalytics.id).label("cnt"))
        .where(OcrAnalytics.failure_reason.isnot(None))
        .group_by(OcrAnalytics.failure_reason)
        .order_by(func.count(OcrAnalytics.id).desc())
        .limit(10)
    )
    failure_reasons = [{"reason": r, "count": c} for r, c in failure_result.fetchall()]

    return {
        "total_users": total_users,
        "total_projects": total_projects,
        "total_events": total_events,
        "top_ocr_failure_reasons": failure_reasons,
    }
