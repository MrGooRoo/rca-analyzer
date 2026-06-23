"""
FastAPI-роутер: анализ инцидентов.

Архитектура:
  API (тонкие роуты)
    → AnalysisPersistenceService (use-case слой)
      → AnalysisService (RCA-анализ + LLM)
      → RCARepository (БД, auto_commit=False, commit на границе use-case)
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.repository import compute_incident_hash
from src.domain.models import (
    AnalysisRequest,
    AnalysisSession,
    ComparisonResult,
    LLMResponseValidationError,
    MethodologyNotSupportedError,
    MultiAnalysisRequest,
    MultiAnalysisResponse,
    RCAResult,
    SimilarIncident,
)
from src.services.analysis_persistence_service import (
    AnalysisPersistenceService,
    load_llm_settings,
    with_heartbeat,
)
from src.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

_service = AnalysisService()
_persistence = AnalysisPersistenceService(service_getter=lambda: _service)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


def _check_owner_or_admin(result: RCAResult, current_user: UserInfo) -> None:
    if current_user.role == "admin":
        return
    if not result.user_id or result.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


def _compare_results(
    results: list[RCAResult], current_user: CurrentUser,
) -> ComparisonResult:
    if len(results) < 2:
        raise HTTPException(status_code=400, detail="Для сравнения нужно минимум 2 результата")
    for r in results:
        _check_owner_or_admin(r, current_user)
    return _service.compare(results)


def _user_id_filter(current_user: UserInfo) -> str | None:
    return None if current_user.role == "admin" else current_user.user_id


# ---------------------------------------------------------------------------
# POST /api/v1/analyze
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=RCAResult, status_code=status.HTTP_201_CREATED)
async def analyze_incident(
    request: AnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    llm_settings = await load_llm_settings(db)
    try:
        return await _persistence.run_single(
            request, current_user.user_id, llm_settings=llm_settings, db=db,
        )
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc


# ---------------------------------------------------------------------------
# POST /api/v1/analyze-stream  — SSE прогресс для одиночного анализа
# ---------------------------------------------------------------------------

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/analyze-stream", status_code=status.HTTP_200_OK)
async def analyze_stream(
    request: AnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    llm_settings = await load_llm_settings(db)

    async def event_generator():
        async for chunk in with_heartbeat(_persistence.stream_single(
            request, current_user.user_id, llm_settings=llm_settings,
        )):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ---------------------------------------------------------------------------
# POST /api/v1/analyze-multi
# ---------------------------------------------------------------------------

@router.post("/analyze-multi", response_model=MultiAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_multi(
    request: MultiAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MultiAnalysisResponse:
    llm_settings = await load_llm_settings(db)
    try:
        return await _persistence.run_multi(
            request, current_user.user_id, llm_settings=llm_settings, db=db,
        )
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

@router.post("/analyze-multi-stream", status_code=status.HTTP_200_OK)
async def analyze_multi_stream(
    request: MultiAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    llm_settings = await load_llm_settings(db)

    async def event_generator():
        async for chunk in with_heartbeat(_persistence.stream_multi(
            request, current_user.user_id, llm_settings=llm_settings,
        )):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ---------------------------------------------------------------------------
# GET /api/v1/methodologies
# ---------------------------------------------------------------------------

@router.get("/methodologies")
async def list_methodologies() -> dict:
    return {"supported": [m.value for m in _service.supported_methodologies()]}


# ---------------------------------------------------------------------------
# GET /api/v1/results
# ---------------------------------------------------------------------------

@router.get("/results", response_model=list[RCAResult])
async def list_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RCAResult]:
    return await _persistence.list_results(
        db, user_id=_user_id_filter(current_user),
        incident_id=incident_id, limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/results/compare  (ДО /results/{result_id})
# ---------------------------------------------------------------------------

@router.get("/results/compare", response_model=ComparisonResult)
async def compare_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: str | None = Query(None),
    session_id: str | None = Query(None),
) -> ComparisonResult:
    if session_id:
        session = await _persistence.get_session(session_id, db)
        if session is None:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        return _compare_results(session.results, current_user)

    if incident_id:
        results = await _persistence.list_results(
            db, user_id=_user_id_filter(current_user), incident_id=incident_id,
        )
        return _compare_results(results, current_user)

    raise HTTPException(status_code=400, detail="Укажите incident_id или session_id")


# ---------------------------------------------------------------------------
# GET /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.get("/results/{result_id}", response_model=RCAResult)
async def get_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    result = await _persistence.get_result(result_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    _check_owner_or_admin(result, current_user)
    return result


# ---------------------------------------------------------------------------
# DELETE /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.delete("/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    result = await _persistence.get_result(result_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    _check_owner_or_admin(result, current_user)
    deleted = await _persistence.delete_result(result_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Результат не найден")


# ---------------------------------------------------------------------------
# PATCH /api/v1/results/{result_id}/recommendations/{rec_id}
# ---------------------------------------------------------------------------

class RecommendationStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "done", "cancelled", "closed"]


@router.patch("/results/{result_id}/recommendations/{rec_id}")
async def update_recommendation_status(
    result_id: str,
    rec_id: str,
    body: RecommendationStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    result = await _persistence.get_result(result_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    _check_owner_or_admin(result, current_user)
    updated = await _persistence.update_recommendation_status(result_id, rec_id, body.status, db)
    if not updated:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена")
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/v1/sessions
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[AnalysisSession])
async def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[AnalysisSession]:
    return await _persistence.list_sessions(
        db, user_id=_user_id_filter(current_user), limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_model=AnalysisSession)
async def get_session(
    session_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> AnalysisSession:
    session = await _persistence.get_session(session_id, db)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    if current_user.role != "admin":
        if session.user_id and session.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
    return session


# ---------------------------------------------------------------------------
# GET /api/v1/incidents/similar  (deprecated)
# ---------------------------------------------------------------------------

@router.get("/incidents/similar", response_model=list[SimilarIncident])
async def find_similar_incidents_get(
    db: DbSession,
    current_user: CurrentUser,
    text: str = Query(..., min_length=3),
    limit: int = Query(5, ge=1, le=50),
    threshold: float | None = Query(None),
    exclude_result_id: str | None = Query(None),
    exclude_incident_id: str | None = Query(None),
) -> list[SimilarIncident]:
    return await _persistence.find_similar_incidents(
        text=text, db=db, user_id=_user_id_filter(current_user),
        limit=limit, threshold=threshold or 0.15,
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


@router.post("/incidents/similar", response_model=list[SimilarIncident])
async def find_similar_incidents(
    body: SimilarIncidentsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[SimilarIncident]:
    exclude_hash = None
    if body.incident_title and body.incident_description:
        exclude_hash = compute_incident_hash(body.incident_title, body.incident_description)

    return await _persistence.find_similar_incidents(
        text=body.text, db=db, user_id=_user_id_filter(current_user),
        limit=body.limit, threshold=body.threshold or 0.15,
        exclude_result_id=body.exclude_result_id,
        exclude_incident_id=body.exclude_incident_id,
        exclude_incident_hash=exclude_hash,
    )
