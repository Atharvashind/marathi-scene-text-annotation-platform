import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    default_language: str = "Marathi"


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    default_language: Optional[str] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str]
    default_language: str
    created_at: datetime
    updated_at: datetime
    image_count: int = 0
    approved_count: int = 0

    model_config = {"from_attributes": True}
