from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.auth.dependencies import get_current_user
from backend.models import User
from backend.users.schemas import UserResponse, UpdateNameRequest, ChangePasswordRequest
from backend.users import service as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return await user_service.get_profile(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateNameRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.update_name(user, body, db)


@router.post("/me/password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.change_password(user, body, db)
