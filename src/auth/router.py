"""
Роутер авторизации: /api/v1/auth/register, /login, /me
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import get_db
from src.auth.models import LoginRequest, RegisterRequest, TokenResponse, UserInfo
from src.auth.service import (
    authenticate_user,
    create_token,
    get_current_user,
    register_user,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: Db) -> TokenResponse:
    """Зарегистрировать нового пользователя и вернуть JWT."""
    user  = await register_user(db, body.email, body.display_name, body.password)
    token = create_token(user.id, user.email, user.display_name)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Db) -> TokenResponse:
    """Выдать JWT по email + password."""
    user  = await authenticate_user(db, body.email, body.password)
    token = create_token(user.id, user.email, user.display_name)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
    )


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    """Информация о текущем пользователе."""
    return current_user
