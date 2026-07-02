import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AnalyticsEvent, OcrAnalytics, AnnotationSession, User
from backend.analytics.providers.base import BaseAnalyticsProvider, InternalOnlyProvider


def _get_external_provider() -> BaseAnalyticsProvider:
    provider_name = os.environ.get("ANALYTICS_PROVIDER", "internal").lower()
    if provider_name == "internal":
        return InternalOnlyProvider()
    # Future: posthog, mixpanel, opentelemetry
    return InternalOnlyProvider()


_external_provider = _get_external_provider()


class TelemetryService:

    async def record(
        self,
        event_type: str,
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        image_id: Optional[uuid.UUID] = None,
        ocr_engine: Optional[str] = None,
        model_version: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[AnalyticsEvent]:
        # Check opt-out
        if user_id:
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.analytics_opt_out:
                return None

        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            project_id=project_id,
            image_id=image_id,
            ocr_engine=ocr_engine,
            model_version=model_version,
            duration_ms=duration_ms,
            event_metadata=metadata or {},
        )
        db.add(event)
        await db.flush()

        # Fire-and-forget to external provider
        asyncio.create_task(
            _external_provider.track(
                event_type,
                str(user_id) if user_id else None,
                {"project_id": str(project_id), **(metadata or {})},
            )
        )
        return event

    async def record_ocr_analytics(
        self,
        event: AnalyticsEvent,
        db: AsyncSession,
        **kwargs,
    ) -> None:
        ocr_analytics = OcrAnalytics(
            event_id=event.event_id,
            image_id=event.image_id,
            **kwargs,
        )
        db.add(ocr_analytics)
        await db.flush()

    async def open_session(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        image_id: uuid.UUID,
        db: AsyncSession,
    ) -> AnnotationSession:
        session = AnnotationSession(
            user_id=user_id,
            project_id=project_id,
            image_id=image_id,
            start_time=datetime.now(timezone.utc),
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def close_session(
        self,
        session_id: uuid.UUID,
        db: AsyncSession,
        **kwargs,
    ) -> None:
        from sqlalchemy import select
        result = await db.execute(
            select(AnnotationSession).where(AnnotationSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return
        session.end_time = datetime.now(timezone.utc)
        if session.start_time:
            delta = session.end_time - session.start_time.replace(tzinfo=timezone.utc)
            session.duration = int(delta.total_seconds())
        for k, v in kwargs.items():
            if hasattr(session, k):
                setattr(session, k, v)
        await db.flush()


telemetry = TelemetryService()
