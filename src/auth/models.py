"""Pydantic-схемы для авторизации."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserInfo(BaseModel):
    user_id: str
    email: str
    display_name: str


class AuthResponse(UserInfo):
    """Ответ успешной авторизации.

    Access/refresh-токены не возвращаются в JSON, а устанавливаются как httpOnly cookie.
    """
