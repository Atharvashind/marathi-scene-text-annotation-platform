from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import User
from backend.auth.service import verify_password, hash_password
from backend.users.schemas import UpdateNameRequest, ChangePasswordRequest, UserResponse


async def get_profile(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


async def update_name(user: User, data: UpdateNameRequest, db: AsyncSession) -> UserResponse:
    user.name = data.name
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def change_password(
    user: User, data: ChangePasswordRequest, db: AsyncSession
) -> dict:
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change password for OAuth-only accounts",
        )
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Password changed successfully"}
