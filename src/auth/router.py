"""Роутер авторизации: register, login, me, refresh, logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.cookies import (
    REFRESH_COOKIE_NAME,
    clear_auth_cookies,
    set_access_cookie,
    set_refresh_cookie,
)
from src.auth.csrf import clear_csrf_cookie, set_csrf_cookie
from src.auth.models import AuthResponse, LoginRequest, RegisterRequest, UserInfo
from src.auth.service import (
    ACCESS_TOKEN_TTL,
    REFRESH_TOKEN_TTL,
    authenticate_user,
    build_user_info,
    get_current_user,
    issue_auth_tokens,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from src.db.base import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
Db = Annotated[AsyncSession, Depends(get_db)]


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, response: Response, db: Db) -> AuthResponse:
    """Зарегистрировать нового пользователя и установить auth-cookie."""
    user = await register_user(db, body.email, body.display_name, body.password)
    access_token, refresh_token = await issue_auth_tokens(db, user)
    set_access_cookie(response, access_token, ACCESS_TOKEN_TTL)
    set_refresh_cookie(response, refresh_token, REFRESH_TOKEN_TTL)
    set_csrf_cookie(response)
    return AuthResponse(**build_user_info(user).model_dump())


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response, db: Db) -> AuthResponse:
    """Вход по email + password. Токены устанавливаются в httpOnly cookie."""
    user = await authenticate_user(db, body.email, body.password)
    access_token, refresh_token = await issue_auth_tokens(db, user)
    set_access_cookie(response, access_token, ACCESS_TOKEN_TTL)
    set_refresh_cookie(response, refresh_token, REFRESH_TOKEN_TTL)
    set_csrf_cookie(response)
    return AuthResponse(**build_user_info(user).model_dump())


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, response: Response, db: Db) -> AuthResponse:
    """Обновить access-token по refresh-token cookie и выполнить rotation."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user, access_token, new_refresh_token = await rotate_refresh_token(db, refresh_token)
    set_access_cookie(response, access_token, ACCESS_TOKEN_TTL)
    set_refresh_cookie(response, new_refresh_token, REFRESH_TOKEN_TTL)
    set_csrf_cookie(response)
    return AuthResponse(**build_user_info(user).model_dump())


@router.post("/logout")
async def logout(request: Request, response: Response, db: Db) -> dict:
    """Очистить cookies и отозвать текущий refresh-token, если он был."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    clear_auth_cookies(response)
    clear_csrf_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    """Информация о текущем пользователе."""
    return current_user
