from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ── Image schemas ──────────────────────────────────────────────────────────────

class ImageResponse(BaseModel):
    id: int
    filename: str
    filepath: str
    width: int
    height: int
    status: str
    upload_date: datetime
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ImageStatusUpdate(BaseModel):
    status: Literal["Uploaded", "OCR_Completed", "Under_Review", "Approved"]


# ── Annotation schemas ─────────────────────────────────────────────────────────

LabelType = Literal["Marathi", "English", "Numeric", "Mixed", "Logo"]


class AnnotationCreate(BaseModel):
    x1: float = Field(..., ge=0)
    y1: float = Field(..., ge=0)
    x2: float = Field(..., ge=0)
    y2: float = Field(..., ge=0)
    text: str = ""
    label: LabelType = "Marathi"


class AnnotationUpdate(BaseModel):
    text: Optional[str] = None
    label: Optional[LabelType] = None
    accepted: Optional[bool] = None
    # Bounding box coordinate updates (used when drag/resize occurs on canvas)
    x1: Optional[float] = Field(None, ge=0)
    y1: Optional[float] = Field(None, ge=0)
    x2: Optional[float] = Field(None, ge=0)
    y2: Optional[float] = Field(None, ge=0)


class AnnotationResponse(BaseModel):
    id: int
    image_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    text: str
    label: str
    confidence: float
    accepted: bool
    ocr_generated: bool
    is_corrected: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Upload result ──────────────────────────────────────────────────────────────

class UploadFileResult(BaseModel):
    filename: str
    success: bool
    image: Optional[ImageResponse] = None
    error: Optional[str] = None


# ── Metrics schemas ────────────────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    image_id: int
    aar: Optional[float] = None   # null when no OCR annotations
    bcr: Optional[float] = None
    mar: Optional[float] = None
    tse: Optional[float] = None   # seconds saved
    total_ocr: int = 0
    total_annotations: int = 0
    high_confidence_count: int = 0   # confidence > 0.95
    low_confidence_count: int = 0    # confidence < 0.80


class ProjectMetricsResponse(BaseModel):
    total_images: int = 0
    total_annotations: int = 0
    average_confidence: Optional[float] = None
    mean_aar: Optional[float] = None
    mean_bcr: Optional[float] = None
    mean_mar: Optional[float] = None
    mean_tse: Optional[float] = None
