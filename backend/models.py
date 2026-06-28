from datetime import datetime
from typing import Optional, List
from sqlalchemy import ForeignKey, String, Integer, Float, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="Uploaded")
    upload_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    annotations: Mapped[List["Annotation"]] = relationship(
        "Annotation", back_populates="image", lazy="selectin"
    )


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("images.id"), nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False, default="")
    label: Mapped[str] = mapped_column(String, nullable=False, default="Marathi")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    image: Mapped["Image"] = relationship("Image", back_populates="annotations")
