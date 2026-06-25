"""
User-facing model catalog: grouped by context size.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.orm_models import ProviderModelORM, ProviderORM, UserORM

router = APIRouter(prefix="/api/v1/user", tags=["user-models"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]

FULL_MIN = 64000          # ≥64K  → Полное
BALANCED_MIN = 16000      # 16K–63K → Сбалансированное
# <16K → Экспресс


class ModelItem(BaseModel):
    model_id: str
    name: str
    context_length: int = 0
    is_free: bool = True
    pricing_prompt: float | None = None
    pricing_completion: float | None = None


class ModelCategory(BaseModel):
    label: str
    icon: str
    context_min: int | None = None
    context_max: int | None = None
    models: list[ModelItem] = []


class ModelsResponse(BaseModel):
    provider: dict[str, Any] | None = None
    categories: dict[str, ModelCategory] = {}


def _classify(ctx: int) -> str:
    if ctx >= FULL_MIN:
        return "full"
    elif ctx >= BALANCED_MIN:
        return "balanced"
    return "express"


CATEGORIES = {
    "full":     {"label": "Полное",     "icon": "FileText",      "context_min": FULL_MIN},
    "balanced": {"label": "Сбалансированное", "icon": "EqualApprox", "context_min": BALANCED_MIN, "context_max": FULL_MIN - 1},
    "express":  {"label": "Экспресс",   "icon": "Zap",           "context_max": BALANCED_MIN - 1},
}


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="Модели активного провайдера, сгруппированные по контексту",
)
async def list_user_models(
    db: DbSession,
    current_user: CurrentUser,
) -> ModelsResponse:
    # Найти активного провайдера (первый с is_active=true)
    provider = (
        await db.execute(
            select(ProviderORM).where(ProviderORM.is_active == True).limit(1)
        )
    ).scalars().first()

    if not provider:
        return ModelsResponse()

    # Получить модели провайдера
    rows = (
        await db.execute(
            select(ProviderModelORM)
            .where(ProviderModelORM.provider_id == provider.id)
            .order_by(ProviderModelORM.context_length.desc(), ProviderModelORM.name)
        )
    ).scalars().all()

    # Группировать
    groups: dict[str, list[ModelItem]] = {k: [] for k in CATEGORIES}
    for m in rows:
        cat = _classify(m.context_length or 0)
        groups[cat].append(
            ModelItem(
                model_id=m.model_id,
                name=m.name,
                context_length=m.context_length or 0,
                is_free=m.is_free if m.is_free is not None else True,
                pricing_prompt=m.pricing_prompt,
                pricing_completion=m.pricing_completion,
            )
        )

    return ModelsResponse(
        provider={"id": provider.id, "name": provider.name},
        categories={
            key: ModelCategory(models=models, **CATEGORIES[key])
            for key, models in groups.items()
        },
    )


# ---------------------------------------------------------------------------
# Предпочтения пользователя по моделям
# ---------------------------------------------------------------------------

class ModelPreferencesUpdate(BaseModel):
    full: str | None = None
    balanced: str | None = None
    express: str | None = None


@router.get(
    "/model-preferences",
    response_model=ModelPreferencesUpdate,
    summary="Получить выбранные пользователем модели",
)
async def get_model_preferences(
    db: DbSession,
    current_user: CurrentUser,
) -> ModelPreferencesUpdate:
    user = await db.get(UserORM, current_user.user_id)
    prefs = user.model_preferences or {}
    return ModelPreferencesUpdate(
        full=prefs.get("full"),
        balanced=prefs.get("balanced"),
        express=prefs.get("express"),
    )


@router.put(
    "/model-preferences",
    response_model=ModelPreferencesUpdate,
    summary="Сохранить выбранные пользователем модели",
)
async def set_model_preferences(
    body: ModelPreferencesUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ModelPreferencesUpdate:
    user = await db.get(UserORM, current_user.user_id)
    prefs = {}
    if body.full:
        prefs["full"] = body.full
    if body.balanced:
        prefs["balanced"] = body.balanced
    if body.express:
        prefs["express"] = body.express
    user.model_preferences = prefs
    await db.commit()
    await db.refresh(user)
    return ModelPreferencesUpdate(
        full=prefs.get("full"),
        balanced=prefs.get("balanced"),
        express=prefs.get("express"),
    )
