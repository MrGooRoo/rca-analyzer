"""
JWT-авторизация: выдача токенов, проверка, хэширование паролей.

passlib 1.7.x не совместим с bcrypt>=4.x — используем bcrypt напрямую.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.db.base import get_db
from src.db.orm_models import UserORM
from src.auth.models import UserInfo

# ---- Конфиг -----------------------------------------------------------------
SECRET_KEY: str   = os.environ.get("JWT_SECRET", "change-me-in-production-please")
ALGORITHM        = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=int(os.environ.get("JWT_TTL_HOURS", "24")))

bearer = HTTPBearer(auto_error=False)

# ---- Хэширование (чистый bcrypt без passlib) --------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# ---- JWT --------------------------------------------------------------------

def create_token(user_id: str, email: str, display_name: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": display_name,
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

# ---- FastAPI Depends --------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload  = decode_token(credentials.credentials)
    user_id  = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Bad token payload")

    user = await db.get(UserORM, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return UserInfo(user_id=user.id, email=user.email, display_name=user.display_name)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserInfo]:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

# ---- DB-операции ------------------------------------------------------------

async def register_user(
    db: AsyncSession,
    email: str,
    display_name: str,
    password: str,
) -> UserORM:
    existing = (await db.execute(
        select(UserORM).where(UserORM.email == email)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserORM(
        id=str(uuid.uuid4()),
        email=email,
        display_name=display_name,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> UserORM:
    user = (await db.execute(
        select(UserORM).where(UserORM.email == email)
    )).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user
