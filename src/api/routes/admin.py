"""
Admin-роутер: управление пользователями.

Все эндпоинты доступны только пользователям с role='admin'.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user, require_admin
from src.db.base import get_db
from src.db.orm_models import UserORM

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]

VALID_ROLES = {"user", "admin"}


# ---------------------------------------------------------------------------
# Pydantic-схемы
# ---------------------------------------------------------------------------

class UserListItem(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
    is_active: bool


class RoleUpdate(BaseModel):
    role: str


# ---------------------------------------------------------------------------
# GET /api/v1/admin/users — список пользователей
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=list[UserListItem],
    summary="Список всех пользователей (admin-only)",
)
async def list_users(
    db: DbSession,
    current_user: CurrentUser,
) -> list[UserListItem]:
    require_admin(current_user)
    rows = (
        await db.execute(select(UserORM).order_by(UserORM.created_at))
    ).scalars().all()
    return [
        UserListItem(
            user_id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
        )
        for u in rows
    ]


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/users/{user_id}/role — изменить роль
# ---------------------------------------------------------------------------

@router.put(
    "/users/{user_id}/role",
    response_model=UserListItem,
    summary="Изменить роль пользователя (admin-only)",
)
async def update_user_role(
    user_id: str,
    body: RoleUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> UserListItem:
    require_admin(current_user)

    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Роль должна быть одной из: {sorted(VALID_ROLES)}",
        )

    # Нельзя снять admin с самого себя
    if user_id == current_user.user_id and body.role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Нельзя снять роль admin с самого себя",
        )

    user = await db.get(UserORM, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.execute(
        update(UserORM).where(UserORM.id == user_id).values(role=body.role)
    )
    await db.commit()
    await db.refresh(user)

    return UserListItem(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )
