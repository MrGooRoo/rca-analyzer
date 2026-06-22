"""
JWT/cookie-авторизация: выдача access-token, refresh-rotation, проверка, хэширование паролей.

passlib 1.7.x не совместим с bcrypt>=4.x — используем bcrypt напрямую.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.cookies import ACCESS_COOKIE_NAME
from src.auth.models import UserInfo
from src.db.base import get_db
from src.db.orm_models import RefreshTokenORM, UserORM

# ---- Конфиг -----------------------------------------------------------------
SECRET_KEY: str = os.environ.get("JWT_SECRET", "change-me-in-production-please")
ALGORITHM = "HS256"

# Максимум неудачных попыток входа перед блокировкой на LOCKOUT_MINUTES минут
MAX_FAILED_LOGIN_ATTEMPTS: int = int(os.environ.get("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
LOCKOUT_MINUTES: int = int(os.environ.get("LOCKOUT_MINUTES", "15"))

if "ACCESS_TOKEN_TTL_MINUTES" in os.environ:
    _access_minutes = int(os.environ["ACCESS_TOKEN_TTL_MINUTES"])
elif "JWT_TTL_HOURS" in os.environ:
    _access_minutes = int(os.environ["JWT_TTL_HOURS"]) * 60
else:
    _access_minutes = 15

ACCESS_TOKEN_TTL = timedelta(minutes=_access_minutes)
REFRESH_TOKEN_TTL = timedelta(days=int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "30")))

bearer = HTTPBearer(auto_error=False)


# ---- Время ------------------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# ---- Хэширование паролей (чистый bcrypt без passlib) ------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---- Access JWT -------------------------------------------------------------
def create_access_token(user_id: str, email: str, display_name: str, role: str = "user") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": display_name,
        "role": role,
        "exp": utcnow() + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---- Refresh token ----------------------------------------------------------
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def build_user_info(user: UserORM) -> UserInfo:
    return UserInfo(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


async def create_refresh_token(db: AsyncSession, user_id: str) -> str:
    raw_token = generate_refresh_token()
    refresh_orm = RefreshTokenORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=utcnow() + REFRESH_TOKEN_TTL,
    )
    db.add(refresh_orm)
    await db.commit()
    return raw_token


async def issue_auth_tokens(db: AsyncSession, user: UserORM) -> tuple[str, str]:
    access_token = create_access_token(user.id, user.email, user.display_name, user.role)
    refresh_token = await create_refresh_token(db, user.id)
    return access_token, refresh_token


async def rotate_refresh_token(
    db: AsyncSession,
    refresh_token: str,
) -> tuple[UserORM, str, str]:
    token_hash = hash_refresh_token(refresh_token)
    stmt = select(RefreshTokenORM).where(RefreshTokenORM.token_hash == token_hash)
    token_row = (await db.execute(stmt)).scalar_one_or_none()

    now = utcnow()
    if token_row is None or token_row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    if ensure_utc(token_row.expires_at) <= now:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await db.get(UserORM, token_row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    token_row.revoked_at = now

    new_refresh_token = generate_refresh_token()
    db.add(
        RefreshTokenORM(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=hash_refresh_token(new_refresh_token),
            expires_at=now + REFRESH_TOKEN_TTL,
        )
    )
    await db.commit()

    access_token = create_access_token(user.id, user.email, user.display_name, user.role)
    return user, access_token, new_refresh_token


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> None:
    stmt = select(RefreshTokenORM).where(
        RefreshTokenORM.token_hash == hash_refresh_token(refresh_token)
    )
    token_row = (await db.execute(stmt)).scalar_one_or_none()
    if token_row is None or token_row.revoked_at is not None:
        return

    token_row.revoked_at = utcnow()
    await db.commit()


# ---- FastAPI Depends --------------------------------------------------------
def extract_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    cookie_token = request.cookies.get(ACCESS_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if credentials is not None:
        return credentials.credentials
    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    token = extract_access_token(request, credentials)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Bad token payload")

    user = await db.get(UserORM, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return build_user_info(user)


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> UserInfo | None:
    token = extract_access_token(request, credentials)
    if token is None:
        return None
    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None


# ---- Утилита: require_admin -------------------------------------------------
def require_admin(current_user: UserInfo) -> None:
    """Выбросить 403, если пользователь не admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")


# ---- DB-операции ------------------------------------------------------------
async def register_user(
    db: AsyncSession,
    email: str,
    display_name: str,
    password: str,
) -> UserORM:
    normalized_email = email.strip().lower()
    existing = (
        await db.execute(select(UserORM).where(UserORM.email == normalized_email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = UserORM(
        id=str(uuid.uuid4()),
        email=normalized_email,
        display_name=display_name.strip(),
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
    normalized_email = email.strip().lower()
    user = (
        await db.execute(select(UserORM).where(UserORM.email == normalized_email))
    ).scalar_one_or_none()

    now = utcnow()

    # Проверка блокировки аккаунта
    if user is not None and user.locked_until is not None:
        if ensure_utc(user.locked_until) > now:
            remaining = int((ensure_utc(user.locked_until) - now).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Аккаунт заблокирован. Повторите через {remaining} секунд.",
            )
        # Блокировка истекла — сбрасываем счётчик
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

    if user is None or not verify_password(password, user.hashed_password):
        # Неудачная попытка — увеличиваем счётчик
        if user is not None:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Аккаунт заблокирован на {LOCKOUT_MINUTES} минут из-за множества неудачных попыток входа.",
                )
            await db.commit()
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Успешный вход — сбрасываем счётчик попыток
    if user.failed_login_attempts or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

    return user
