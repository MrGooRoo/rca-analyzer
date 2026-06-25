"""
Admin-роутер: управление пользователями.

Все эндпоинты доступны только пользователям с role='admin'.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user, require_admin
from src.db.base import get_db
from src.db.cache_repository import ExtractionCacheRepository
from src.db.llm_settings_repository import LLMSettingsRepository
from src.db.orm_models import ProviderModelORM, ProviderORM, UserORM
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
    balance: float = 0.0


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
            balance=float(u.balance or 0),
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


# ---------------------------------------------------------------------------
# CRUD провайдеров LLM
# ---------------------------------------------------------------------------

class ProviderCreate(BaseModel):
    name: str
    api_key: str | None = None
    base_url: str | None = None
    is_active: bool = True


class ProviderUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    is_active: bool | None = None


class ProviderRead(BaseModel):
    id: str
    name: str
    api_key_masked: str | None = None
    base_url: str | None = None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


def _mask_api_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return key[:4] + "****"
    return key[:4] + "****" + key[-4:]


def _provider_to_read(p: ProviderORM) -> ProviderRead:
    return ProviderRead(
        id=p.id,
        name=p.name,
        api_key_masked=_mask_api_key(p.api_key),
        base_url=p.base_url,
        is_active=p.is_active,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


@router.get(
    "/providers",
    response_model=list[ProviderRead],
    summary="Список провайдеров LLM (admin-only)",
)
async def list_providers(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProviderRead]:
    require_admin(current_user)
    rows = (await db.execute(select(ProviderORM).order_by(ProviderORM.name))).scalars().all()
    return [_provider_to_read(p) for p in rows]


@router.post(
    "/providers",
    response_model=ProviderRead,
    status_code=201,
    summary="Добавить провайдера LLM (admin-only)",
)
async def create_provider(
    body: ProviderCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProviderRead:
    require_admin(current_user)
    record = ProviderORM(
        id=str(uuid.uuid4()),
        name=body.name.strip(),
        api_key=body.api_key.strip() if body.api_key else None,
        base_url=body.base_url.strip() if body.base_url else None,
        is_active=body.is_active,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _provider_to_read(record)


@router.put(
    "/providers/{provider_id}",
    response_model=ProviderRead,
    summary="Обновить провайдера LLM (admin-only)",
)
async def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProviderRead:
    require_admin(current_user)
    record = await db.get(ProviderORM, provider_id)
    if not record:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    if body.name is not None:
        record.name = body.name.strip()
    if body.api_key is not None:
        record.api_key = body.api_key.strip() if body.api_key else None
    if body.base_url is not None:
        record.base_url = body.base_url.strip() if body.base_url else None
    if body.is_active is not None:
        record.is_active = body.is_active
    await db.commit()
    await db.refresh(record)
    return _provider_to_read(record)


@router.delete(
    "/providers/{provider_id}",
    status_code=204,
    summary="Удалить провайдера LLM (admin-only)",
)
async def delete_provider(
    provider_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    require_admin(current_user)
    record = await db.get(ProviderORM, provider_id)
    if not record:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    await db.delete(record)
    await db.commit()


# ---------------------------------------------------------------------------
# Сканирование и список моделей провайдера
# ---------------------------------------------------------------------------

class ProviderModelRead(BaseModel):
    id: str
    provider_id: str
    model_id: str
    name: str
    context_length: int = 0
    is_free: bool = True
    pricing_prompt: float | None = None
    pricing_completion: float | None = None
    created_at: str | None = None


def _model_to_read(m: ProviderModelORM) -> ProviderModelRead:
    return ProviderModelRead(
        id=m.id,
        provider_id=m.provider_id,
        model_id=m.model_id,
        name=m.name,
        context_length=m.context_length or 0,
        is_free=m.is_free if m.is_free is not None else True,
        pricing_prompt=m.pricing_prompt,
        pricing_completion=m.pricing_completion,
        created_at=m.created_at.isoformat() if m.created_at else None,
    )


@router.get(
    "/providers/{provider_id}/models",
    response_model=list[ProviderModelRead],
    summary="Список моделей провайдера (admin-only)",
)
async def list_provider_models(
    provider_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProviderModelRead]:
    require_admin(current_user)
    provider = await db.get(ProviderORM, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    rows = (
        await db.execute(
            select(ProviderModelORM)
            .where(ProviderModelORM.provider_id == provider_id)
            .order_by(ProviderModelORM.name)
        )
    ).scalars().all()
    return [_model_to_read(m) for m in rows]


@router.post(
    "/providers/{provider_id}/scan",
    response_model=list[ProviderModelRead],
    summary="Сканировать каталог провайдера и обновить список моделей (admin-only)",
)
async def scan_provider_models(
    provider_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProviderModelRead]:
    require_admin(current_user)
    import httpx

    provider = await db.get(ProviderORM, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    if not provider.api_key:
        raise HTTPException(status_code=400, detail="У провайдера не указан API-ключ")

    base_url = (provider.base_url or "https://openrouter.ai/api/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {provider.api_key}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка при запросе к провайдеру: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось разобрать ответ провайдера: {exc}") from exc

    models_raw = data.get("data", [])
    if not models_raw:
        raise HTTPException(status_code=502, detail="Провайдер не вернул список моделей")

    # Удаляем старые модели и вставляем новые
    old = (
        await db.execute(select(ProviderModelORM).where(ProviderModelORM.provider_id == provider_id))
    ).scalars().all()
    for rec in old:
        await db.delete(rec)
    await db.flush()  # применить DELETE до INSERT

    imported = []
    for m in models_raw:
        mid = (m.get("id") or "").strip()
        name = (m.get("name") or mid or "Unknown").strip()
        if not mid:
            continue
        pricing = m.get("pricing") or {}
        is_free = (
            bool(
                float(pricing.get("prompt") or 0) == 0.0
                and float(pricing.get("completion") or 0) == 0.0
            )
            if isinstance(pricing, dict)
            else False
        )
        record = ProviderModelORM(
            id=str(uuid.uuid4()),
            provider_id=provider_id,
            model_id=mid,
            name=name,
            context_length=int(m.get("context_length", 0) or 0),
            is_free=is_free,
            pricing_prompt=float(pricing.get("prompt")) if isinstance(pricing, dict) and pricing.get("prompt") is not None else None,
            pricing_completion=float(pricing.get("completion")) if isinstance(pricing, dict) and pricing.get("completion") is not None else None,
        )
        db.add(record)
        imported.append(record)

    await db.commit()
    for rec in imported:
        await db.refresh(rec)

    return [_model_to_read(m) for m in imported]
