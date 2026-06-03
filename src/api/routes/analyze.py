"""
FastAPI-роутер: анализ инцидентов.

Результаты хранятся в PostgreSQL через RCARepository.
In-memory кэш удалён.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import get_db
from src.db.repository import RCARepository
from src.domain.models import (
    AnalysisRequest,
    LLMResponseValidationError,
    MethodologyNotSupportedError,
    RCAResult,
)
from src.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])
_service = AnalysisService()

# ---------------------------------------------------------------------------
# Тип для FastAPI Depends (читаемость)
# ---------------------------------------------------------------------------
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# POST /api/v1/analyze
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=RCAResult,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить RCA-анализ инцидента",
    responses={
        400: {"description": "Невалидный запрос или неподдерживаемая методика"},
        422: {"description": "Ошибка валидации входных данных"},
        502: {"description": "LLM вернул невалидный ответ после retry"},
    },
)
async def analyze_incident(
    request: AnalysisRequest,
    db: DbSession,
) -> RCAResult:
    """
    Принять описание инцидента, запустить LLM-анализ и сохранить результат в БД.

    - **methodology**: `five_why` | `rca_systemic` | `ishikawa` | `fta`
    - **detail_level**: 1=кратко, 2=стандарт, 3=подробно
    - **language**: `ru` или `en`
    """
    try:
        result = await _service.analyze(request)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM не вернул валидный ответ. Попробуйте позже.",
        ) from exc

    repo = RCARepository(db)
    await repo.save_result(result)
    logger.info("[DB] saved result %s", result.result_id)

    return result


# ---------------------------------------------------------------------------
# GET /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.get(
    "/results/{result_id}",
    response_model=RCAResult,
    summary="Получить результат анализа из БД",
    responses={404: {"description": "Результат не найден"}},
)
async def get_result(result_id: str, db: DbSession) -> RCAResult:
    """Get RCAResult by ID from PostgreSQL."""
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Результат '{result_id}' не найден.",
        )
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/results  (список с пагинацией)
# ---------------------------------------------------------------------------

@router.get(
    "/results",
    response_model=list[RCAResult],
    summary="Список всех результатов с пагинацией",
)
async def list_results(
    db: DbSession,
    incident_id: str | None = Query(None, description="Фильтр по ID инцидента"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RCAResult]:
    """GET /api/v1/results?limit=20&offset=0&incident_id=..."""
    repo = RCARepository(db)
    return await repo.list_results(incident_id=incident_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# PATCH /api/v1/results/{result_id}/recommendations/{rec_id}
# ---------------------------------------------------------------------------

from pydantic import BaseModel  # noqa: E402


class StatusUpdate(BaseModel):
    status: str  # open | in_progress | closed


@router.patch(
    "/results/{result_id}/recommendations/{rec_id}",
    summary="Обновить статус рекомендации",
    responses={404: {"description": "Рекомендация не найдена"}},
)
async def update_recommendation(
    result_id: str,
    rec_id: str,
    body: StatusUpdate,
    db: DbSession,
) -> dict:
    """
    Изменить статус рекомендации: `open` → `in_progress` → `closed`.
    """
    VALID = {"open", "in_progress", "closed"}
    if body.status not in VALID:
        raise HTTPException(
            status_code=400,
            detail=f"Статус должен быть одним из: {VALID}",
        )
    repo = RCARepository(db)
    updated = await repo.update_recommendation_status(result_id, rec_id, body.status)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"Рекомендация '{rec_id}' в результате '{result_id}' не найдена.",
        )
    return {"result_id": result_id, "rec_id": rec_id, "status": body.status}


# ---------------------------------------------------------------------------
# GET /api/v1/methodologies
# ---------------------------------------------------------------------------

@router.get("/methodologies", summary="Список реализованных методик RCA")
async def list_methodologies() -> dict:
    return {"supported": [m.value for m in _service.supported_methodologies()]}
