import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Request, Cookie
from fastapi.security import HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database import get_db
from backend.models import User
from backend.auth.schemas import SignupRequest, LoginRequest, TokenResponse, ForgotPasswordRequest
from backend.auth import service as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_SETTINGS = {
    "httponly": True,
    "secure": False,   # Set True in production (HTTPS)
    "samesite": "strict",
    "max_age": 60 * 60 * 24 * 7,  # 7 days
}


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(REFRESH_COOKIE_NAME, token, **COOKIE_SETTINGS)


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME)


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await auth_service.get_user_by_email(body.email, db)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=body.name,
        email=body.email,
        password_hash=auth_service.hash_password(body.password),
        last_login=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    access_token = auth_service.create_access_token(user)
    refresh_token = await auth_service.create_refresh_token(user.id, db)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/10minutes")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_email(body.email, db)
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not auth_service.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    access_token = auth_service.create_access_token(user)
    refresh_token = await auth_service.create_refresh_token(user.id, db)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    user = await auth_service.validate_and_rotate_refresh_token(refresh_token, db)
    if not user:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = auth_service.create_access_token(user)
    new_refresh = await auth_service.create_refresh_token(user.id, db)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        await auth_service.invalidate_refresh_token(refresh_token, db)
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    # Placeholder — no email sent in this version
    return {"message": "If that email is registered, a reset link will be sent."}
