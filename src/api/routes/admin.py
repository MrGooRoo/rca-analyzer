"""
Admin-роутер: управление пользователями.

Все эндпоинты доступны только пользователям с role='admin'.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user, require_admin
from src.db.base import get_db
from src.db.cache_repository import ExtractionCacheRepository
from src.db.llm_settings_repository import LLMSettingsRepository
from src.db.orm_models import UserORM
from src.domain.models import LLMSettings, LLMSettingsUpdate, OpenRouterModelInfo
from src.integrations.llm.openrouter_catalog import (
    OpenRouterCatalogError,
    fetch_openrouter_models,
)

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


# ---------------------------------------------------------------------------
# GET/PUT /api/v1/admin/llm-settings — P17 LLM Conductor settings
# ---------------------------------------------------------------------------

@router.get(
    "/llm-settings",
    response_model=LLMSettings,
    summary="Получить настройки LLM Conductor (admin-only)",
)
async def get_llm_settings(
    db: DbSession,
    current_user: CurrentUser,
) -> LLMSettings:
    require_admin(current_user)
    return await LLMSettingsRepository(db).get()


@router.put(
    "/llm-settings",
    response_model=LLMSettings,
    summary="Обновить настройки LLM Conductor (admin-only)",
)
async def update_llm_settings(
    body: LLMSettingsUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LLMSettings:
    require_admin(current_user)
    return await LLMSettingsRepository(db).upsert(body, updated_by=current_user.email)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/openrouter/models — P17 OpenRouter catalog proxy
# ---------------------------------------------------------------------------

@router.get(
    "/openrouter/models",
    response_model=list[OpenRouterModelInfo],
    summary="Каталог моделей OpenRouter для выбора в LLM-настройках (admin-only)",
)
async def list_openrouter_models(
    current_user: CurrentUser,
    search: str | None = Query(default=None, max_length=100),
    free_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    force_refresh: bool = False,
) -> list[OpenRouterModelInfo]:
    require_admin(current_user)
    try:
        return await fetch_openrouter_models(
            search=search,
            free_only=free_only,
            limit=limit,
            force_refresh=force_refresh,
        )
    except OpenRouterCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /api/v1/admin/docx-cache — список кэша извлечений
# ---------------------------------------------------------------------------

class DocxCacheItem(BaseModel):
    file_hash: str
    incident_hash: str | None = None
    created_at: str | None = None
    hit_count: int = 0


@router.get(
    "/docx-cache",
    response_model=list[DocxCacheItem],
    summary="Список всех записей кэша DOCX-извлечений (admin-only)",
)
async def list_docx_cache(
    db: DbSession,
    current_user: CurrentUser,
) -> list[DocxCacheItem]:
    require_admin(current_user)
    repo = ExtractionCacheRepository(db)
    raw = await repo.list_all()
    return [DocxCacheItem(**r) for r in raw]


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/docx-cache/{file_hash} — удалить запись кэша
# ---------------------------------------------------------------------------

@router.delete(
    "/docx-cache/{file_hash}",
    status_code=204,
    summary="Удалить запись из кэша DOCX-извлечений по file_hash (admin-only)",
)
async def delete_docx_cache(
    file_hash: str,
    db: DbSession,
    current_user: CurrentUser,
):
    require_admin(current_user)
    repo = ExtractionCacheRepository(db)
    deleted = await repo.delete(file_hash)
    if not deleted:
        raise HTTPException(status_code=404, detail="Запись не найдена")
