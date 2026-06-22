"""
FastAPI-роутер: анализ инцидентов.

Защищённые эндпоинты требуют auth-cookie или Bearer-токен.
Результаты привязываются к user_id текущего пользователя.

Роли:
  - admin: видит, редактирует и удаляет любые результаты.
  - user:  видит и управляет только своими записями.

Архитектура:
  API (тонкие роуты)
    → AnalysisPersistenceService (use-case слой)
      → AnalysisService (RCA-анализ + LLM)
      → RCARepository (БД, auto_commit=False, commit на границе use-case)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.repository import RCARepository
from src.domain.models import (
    AnalysisRequest,
    AnalysisSession,
    ComparisonResult,
    LLMResponseValidationError,
    MethodologyNotSupportedError,
    MultiAnalysisRequest,
    RCAResult,
    SimilarIncident,
)
from src.services.analysis_persistence_service import (
    AnalysisPersistenceService,
    load_llm_settings,
)
from src.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

# Module-level service instances (backward compat for tests patching _service)
_service = AnalysisService()
_persistence = AnalysisPersistenceService(service_getter=lambda: _service)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


def _check_owner_or_admin(result: RCAResult, current_user: UserInfo) -> None:
    """Проверить, что пользователь — владелец записи или admin."""
    if current_user.role == "admin":
        return
    if result.user_id and result.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


# ---------------------------------------------------------------------------
# POST /api/v1/analyze
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=RCAResult,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить RCA-анализ инцидента",
)
async def analyze_incident(
    request: AnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    llm_settings = await load_llm_settings(db)
    try:
        result = await _persistence.run_single(
            request, current_user.user_id, llm_settings=llm_settings, db=db,
        )
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc

    return result


# ---------------------------------------------------------------------------
# POST /api/v1/analyze-stream  — SSE прогресс для одиночного анализа
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-stream",
    status_code=status.HTTP_200_OK,
    summary="Запустить RCA-анализ инцидента (SSE-статус выполнения)",
)
async def analyze_stream(
    request: AnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """SSE-эндпоинт для одиночного анализа.

    События:
      {"status": "started", "methodology": "five_why", "name": "5 Почему"}
      {"status": "stage", "stage": "preparing", "percent": 10, "message": "..."}
      {"status": "stage", "stage": "llm",       "percent": 40, "message": "..."}
      {"status": "stage", "stage": "parsing",   "percent": 80, "message": "..."}
      {"status": "done",  "result": <RCAResult>}
      {"status": "error", "message": "..."}
    """
    llm_settings = await load_llm_settings(db)

    async def event_generator():
        stream = _persistence.stream_single(
            request, current_user.user_id, llm_settings=llm_settings,
        )
        async for event in stream:
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.02)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /api/v1/analyze-multi
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-multi",
    response_model=list[RCAResult],
    status_code=status.HTTP_201_CREATED,
    summary="Запустить анализ несколькими методиками",
)
async def analyze_multi(
    request: MultiAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[RCAResult]:
    llm_settings = await load_llm_settings(db)
    try:
        results = await _persistence.run_multi(
            request, current_user.user_id, llm_settings=llm_settings, db=db,
        )
        return results
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error in analyze-multi: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc
    except Exception as exc:
        logger.error("[API] Unexpected error in analyze-multi: %s", exc)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера") from exc


# ---------------------------------------------------------------------------
# POST /api/v1/analyze-multi-stream  — SSE прогресс по методологиям
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-multi-stream",
    status_code=status.HTTP_200_OK,
    summary="Запустить анализ несколькими методиками (SSE-поток прогресса)",
)
async def analyze_multi_stream(
    request: MultiAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """SSE-эндпоинт: запускает все методологии параллельно и отправляет события
    по мере завершения каждой. DB-сессии короткоживущие."""
    llm_settings = await load_llm_settings(db)

    async def event_generator():
        async for chunk in _persistence.stream_multi(
            request, current_user.user_id, llm_settings=llm_settings,
        ):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/v1/methodologies
# ---------------------------------------------------------------------------

@router.get("/methodologies", summary="Список реализованных методик RCA")
async def list_methodologies() -> dict:
    svc = AnalysisService()
    return {"supported": [m.value for m in svc.supported_methodologies()]}


# ---------------------------------------------------------------------------
# GET /api/v1/results
# ---------------------------------------------------------------------------

@router.get(
    "/results",
    response_model=list[RCAResult],
    summary="Список результатов (admin — все, user — свои)",
)
async def list_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RCAResult]:
    repo = RCARepository(db)
    user_id_filter = None if current_user.role == "admin" else current_user.user_id
    return await repo.list_results(
        user_id=user_id_filter,
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/results/compare  (ДО /results/{result_id} — порядок важен!)
# ---------------------------------------------------------------------------

@router.get(
    "/results/compare",
    response_model=ComparisonResult,
    summary="Сравнить результаты анализа по сессии",
)
async def compare_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: str | None = Query(None),
    session_id: str | None = Query(None),
) -> ComparisonResult:
    repo = RCARepository(db)

    if session_id:
        session = await repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        results = session.results
    elif incident_id:
        user_id_filter = None if current_user.role == "admin" else current_user.user_id
        results = await repo.list_results(
            user_id=user_id_filter, incident_id=incident_id,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Укажите incident_id или session_id",
        )

    if len(results) < 2:
        raise HTTPException(
            status_code=400,
            detail="Для сравнения нужно минимум 2 результата",
        )
    for r in results:
        _check_owner_or_admin(r, current_user)

    return _service.compare(results)


# ---------------------------------------------------------------------------
# GET /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.get(
    "/results/{result_id}",
    response_model=RCAResult,
    summary="Получить результат анализа",
)
async def get_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    _check_owner_or_admin(result, current_user)
    return result


# ---------------------------------------------------------------------------
# DELETE /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/results/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить результат анализа",
)
async def delete_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    _check_owner_or_admin(result, current_user)
    deleted = await repo.delete_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Результат не найден")


# ---------------------------------------------------------------------------
# PATCH /api/v1/results/{result_id}/recommendations/{rec_id}
# ---------------------------------------------------------------------------

class RecommendationStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


@router.patch(
    "/results/{result_id}/recommendations/{rec_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить статус рекомендации",
)
async def update_recommendation_status(
    result_id: str,
    rec_id: str,
    body: RecommendationStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    _check_owner_or_admin(result, current_user)
    updated = await repo.update_recommendation_status(result_id, rec_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена")
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/v1/sessions
# ---------------------------------------------------------------------------

@router.get(
    "/sessions",
    response_model=list[AnalysisSession],
    summary="Список исследований",
)
async def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[AnalysisSession]:
    repo = RCARepository(db)
    user_id_filter = None if current_user.role == "admin" else current_user.user_id
    return await repo.list_sessions(
        user_id=user_id_filter, limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}",
    response_model=AnalysisSession,
    summary="Получить исследование по ID",
)
async def get_session(
    session_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> AnalysisSession:
    repo = RCARepository(db)
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    if current_user.role != "admin":
        if session.user_id and session.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
    return session


# ---------------------------------------------------------------------------
# GET /api/v1/incidents/similar  (deprecated — используйте POST)
# ---------------------------------------------------------------------------

@router.get(
    "/incidents/similar",
    response_model=list[SimilarIncident],
    summary="[deprecated] Найти похожие инциденты (GET-версия)",
)
async def find_similar_incidents_get(
    db: DbSession,
    current_user: CurrentUser,
    text: str = Query(..., min_length=3),
    limit: int = Query(5, ge=1, le=50),
    threshold: float | None = Query(None),
    exclude_result_id: str | None = Query(None),
    exclude_incident_id: str | None = Query(None),
) -> list[SimilarIncident]:
    repo = RCARepository(db)
    user_id_filter = None if current_user.role == "admin" else current_user.user_id
    t = threshold if threshold is not None else 0.15
    # Lazy backfill: доиндексировать записи без embeddings текущей модели
    await repo.backfill_missing_embeddings(user_id=user_id_filter, limit=100)
    return await repo.find_similar_incidents(
        text=text, user_id=user_id_filter, limit=limit, threshold=t,
        exclude_result_id=exclude_result_id, exclude_incident_id=exclude_incident_id,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/incidents/similar
# ---------------------------------------------------------------------------

class SimilarIncidentsRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=5000)
    incident_title: str | None = Field(default=None, max_length=500)
    incident_description: str | None = Field(default=None, max_length=10000)
    limit: int = Field(default=5, ge=1, le=50)
    threshold: float | None = None
    exclude_result_id: str | None = None
    exclude_incident_id: str | None = None


@router.post(
    "/incidents/similar",
    response_model=list[SimilarIncident],
    summary="Найти похожие инциденты",
)
async def find_similar_incidents(
    body: SimilarIncidentsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[SimilarIncident]:
    repo = RCARepository(db)
    user_id_filter = None if current_user.role == "admin" else current_user.user_id

    threshold_val = body.threshold if body.threshold is not None else 0.15

    # Lazy backfill: доиндексировать записи без embeddings текущей модели
    await repo.backfill_missing_embeddings(user_id=user_id_filter, limit=100)

    exclude_hash = None
    if body.incident_title and body.incident_description:
        from src.db.repository import compute_incident_hash
        exclude_hash = compute_incident_hash(body.incident_title, body.incident_description)

    return await repo.find_similar_incidents(
        text=body.text,
        user_id=user_id_filter,
        limit=body.limit,
        threshold=threshold_val,
        exclude_result_id=body.exclude_result_id,
        exclude_incident_id=body.exclude_incident_id,
        exclude_incident_hash=exclude_hash,
    )
