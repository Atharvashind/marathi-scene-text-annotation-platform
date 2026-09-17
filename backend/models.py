import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Integer, Float, Text, DateTime,
    ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


# ── Users ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    analytics_opt_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="annotator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    projects: Mapped[List["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    analytics_events: Mapped[List["AnalyticsEvent"]] = relationship("AnalyticsEvent", back_populates="user")
    annotation_sessions: Mapped[List["AnnotationSession"]] = relationship("AnnotationSession", back_populates="user")


# ── Projects ───────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_language: Mapped[str] = mapped_column(String(50), nullable=False, default="Marathi")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="projects")
    images: Mapped[List["Image"]] = relationship("Image", back_populates="project", cascade="all, delete-orphan")


# ── Images ─────────────────────────────────────────────────────────────────────

class Image(Base):
    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Uploaded")
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="images")
    annotations: Mapped[List["Annotation"]] = relationship("Annotation", back_populates="image", cascade="all, delete-orphan")


# ── Annotations ────────────────────────────────────────────────────────────────

class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="Marathi")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    image: Mapped["Image"] = relationship("Image", back_populates="annotations")


# ── Refresh Tokens ─────────────────────────────────────────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


# ── Analytics Events ───────────────────────────────────────────────────────────

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    image_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    ocr_engine: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="analytics_events")
    ocr_analytics: Mapped[Optional["OcrAnalytics"]] = relationship("OcrAnalytics", back_populates="event", uselist=False)


# ── OCR Analytics ──────────────────────────────────────────────────────────────

class OcrAnalytics(Base):
    __tablename__ = "ocr_analytics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("analytics_events.event_id", ondelete="CASCADE"), nullable=True, unique=True)
    image_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    number_of_boxes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    average_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accepted_boxes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rejected_boxes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    corrected_boxes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    manual_boxes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    difficulty_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    orientation: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    event: Mapped[Optional["AnalyticsEvent"]] = relationship("AnalyticsEvent", back_populates="ocr_analytics")


# ── Annotation Sessions ────────────────────────────────────────────────────────

class AnnotationSession(Base):
    __tablename__ = "annotation_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    image_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annotations_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    annotations_corrected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    annotations_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zoom_operations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pan_operations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship("User", back_populates="annotation_sessions")
