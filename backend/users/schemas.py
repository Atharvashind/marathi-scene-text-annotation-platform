import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    avatar_url: Optional[str] = None
    role: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UpdateNameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
