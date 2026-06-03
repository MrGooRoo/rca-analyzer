"""
FastAPI-роутер: анализ инцидентов.

Эндпоинты (contracts.md раздел 5):
    POST /api/v1/analyze          — запустить анализ
    GET  /api/v1/results/{id}     — получить результат (in-memory кеш)
    GET  /api/v1/methodologies    — список доступных методик
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, status

from src.domain.models import (
    AnalysisRequest,
    MethodologyNotSupportedError,
    LLMResponseValidationError,
    RCAResult,
)
from src.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

# In-memory хранилище результатов (заменить на Redis/DB в проде)
_results: dict[str, RCAResult] = {}

# Синглтон сервиса (DI через FastAPI Depends при необходимости)
_service = AnalysisService()


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
async def analyze_incident(request: AnalysisRequest) -> RCAResult:
    """
    Принять описание инцидента и вернуть результат RCA-анализа.

    - **methodology**: one of `five_why`, `rca_systemic`, `ishikawa`, `fta`, `bowtie`
    - **detail_level**: 1=кратко, 2=стандарт, 3=подробно
    - **language**: язык отчёта (`ru` или `en`)
    """
    try:
        result = await _service.analyze(request)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM не вернул валидный ответ. Попробуйте позже.",
        ) from exc

    _results[result.result_id] = result
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.get(
    "/results/{result_id}",
    response_model=RCAResult,
    summary="Получить сохранённый результат анализа",
    responses={
        404: {"description": "Результат не найден"},
    },
)
async def get_result(result_id: str) -> RCAResult:
    """Вернуть ранее сохранённый RCAResult по его ID."""
    result = _results.get(result_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Результат '{result_id}' не найден.",
        )
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/methodologies
# ---------------------------------------------------------------------------

@router.get(
    "/methodologies",
    summary="Список реализованных методик RCA",
)
async def list_methodologies() -> dict:
    """Вернуть список методик, доступных для анализа прямо сейчас."""
    return {
        "supported": [m.value for m in _service.supported_methodologies()],
    }
