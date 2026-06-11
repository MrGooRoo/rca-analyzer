"""
FastAPI-роутер: анализ инцидентов.

Защищённые эндпоинты требуют auth-cookie или Bearer-токен.
Результаты привязываются к user_id текущего пользователя.

Роли:
  - admin: видит, редактирует и удаляет любые результаты.
  - user:  видит и управляет только своими записями.
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
    ComparisonResult,
    LLMResponseValidationError,
    MethodologyNotSupportedError,
    MultiAnalysisRequest,
    RCAResult,
    SimilarIncident,
)
from src.services.analysis_service import AnalysisService
from src.services.embedding_service import default_similarity_threshold

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])
_service = AnalysisService()

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]

METHODOLOGY_NAMES_RU = {
    "five_why":     "5 Почему",
    "ishikawa":     "Ishikawa",
    "fta":          "FTA",
    "rca_systemic": "RCA Системный",
    "bowtie":       "BowTie",
}


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
    try:
        result = await _service.analyze(request)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc

    repo = RCARepository(db)
    await repo.save_result(result, user_id=current_user.user_id)
    logger.info("[DB] saved result %s for user %s", result.result_id, current_user.user_id)

    result.user_id = current_user.user_id
    return result


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
    try:
        results = await _service.analyze_multi(request)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error in analyze-multi: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc
    except Exception as exc:
        logger.error("[API] Unexpected error in analyze-multi: %s", exc)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера") from exc

    repo = RCARepository(db)
    for result in results:
        await repo.save_result(result, user_id=current_user.user_id)
        result.user_id = current_user.user_id
    return results


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
    """
    SSE-эндпоинт: запускает все методологии параллельно и отправляет события
    по мере завершения каждой.

    События:
      {"status": "started",   "total": N, "methodologies": [...]}
      {"status": "progress",  "methodology": "bowtie",  "name": "BowTie",  "done": K, "total": N}
      {"status": "error_one", "methodology": "fta",     "name": "FTA",     "message": "..."}
      {"status": "done",      "results": [...]}
      {"status": "error",     "message": "..."}   — фатальная ошибка
    """
    async def event_generator():
        methodologies = request.methodologies
        total = len(methodologies)
        names = [METHODOLOGY_NAMES_RU.get(m.value, m.value) for m in methodologies]

        yield "data: " + json.dumps({
            "status": "started",
            "total": total,
            "methodologies": names,
        }) + "\n\n"
        await asyncio.sleep(0.05)

        import uuid as _uuid
        incident_id = str(_uuid.uuid4())

        # Очередь для результатов по мере готовности
        queue: asyncio.Queue = asyncio.Queue()

        async def run_one(methodology):
            name = METHODOLOGY_NAMES_RU.get(methodology.value, methodology.value)
            single = AnalysisRequest(
                methodology=methodology,
                language=request.language,
                detail_level=request.detail_level,
                incident=request.incident,
            )
            try:
                result = await _service.analyze(single)
                result.incident_id = incident_id
                await queue.put(("ok", methodology, result))
            except Exception as exc:
                logger.error("[AnalyzeMultiStream] %s ошибка: %s", name, exc)
                await queue.put(("err", methodology, str(exc)))

        tasks = [asyncio.create_task(run_one(m)) for m in methodologies]

        results = []
        errors = []
        done_count = 0
        repo = RCARepository(db)

        while done_count < total:
            kind, methodology, payload = await queue.get()
            done_count += 1
            name = METHODOLOGY_NAMES_RU.get(methodology.value, methodology.value)

            if kind == "ok":
                result = payload
                try:
                    await repo.save_result(result, user_id=current_user.user_id)
                    result.user_id = current_user.user_id
                except Exception as exc:
                    logger.error("[AnalyzeMultiStream] Ошибка сохранения %s: %s", name, exc)

                results.append(result)
                yield "data: " + json.dumps({
                    "status": "progress",
                    "methodology": methodology.value,
                    "name": name,
                    "done": done_count,
                    "total": total,
                }) + "\n\n"
            else:
                errors.append(name)
                yield "data: " + json.dumps({
                    "status": "error_one",
                    "methodology": methodology.value,
                    "name": name,
                    "message": payload,
                    "done": done_count,
                    "total": total,
                }) + "\n\n"

            await asyncio.sleep(0.02)

        # Ждём завершения всех задач (на случай исключений вне queue)
        await asyncio.gather(*tasks, return_exceptions=True)

        if not results:
            yield "data: " + json.dumps({
                "status": "error",
                "message": "Все методологии завершились с ошибкой. Проверьте подключение к LLM.",
            }) + "\n\n"
            return

        # Сериализуем через pydantic (datetime → str и т.д.)
        results_json = [r.model_dump(mode="json") for r in results]
        yield "data: " + json.dumps({
            "status": "done",
            "results": results_json,
        }) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/v1/methodologies
# ---------------------------------------------------------------------------

@router.get("/methodologies", summary="Список реализованных методик RCA")
async def list_methodologies() -> dict:
    return {"supported": [m.value for m in _service.supported_methodologies()]}


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
# POST + GET /api/v1/incidents/similar
# ---------------------------------------------------------------------------

class SimilarIncidentsRequest(BaseModel):
    """Тело запроса поиска похожих инцидентов.

    Текст передаётся в теле (POST), а не в query string: длинные описания
    инцидентов в URL приводят к HTTP 431 Request Header Fields Too Large.
    """

    text: str = Field(..., min_length=3, max_length=5000, description="Текст нового инцидента")
    limit: int = Field(5, ge=1, le=20)
    threshold: float | None = Field(
        None, ge=0.0, le=1.0,
        description="Порог похожести; если не задан — подбирается под провайдер эмбеддингов",
    )
    exclude_result_id: str | None = None
    exclude_incident_id: str | None = None


async def _do_find_similar(
    db: AsyncSession,
    current_user: UserInfo,
    *,
    text: str,
    limit: int,
    threshold: float | None,
    exclude_result_id: str | None,
    exclude_incident_id: str | None,
) -> list[SimilarIncident]:
    repo = RCARepository(db)
    user_filter = None if current_user.role == "admin" else current_user.user_id
    # У hashing-эмбеддингов несвязанные тексты ~0, у нейросетевых ~0.4-0.5 —
    # дефолтный порог зависит от EMBEDDINGS_PROVIDER (см. embedding_service).
    effective_threshold = threshold if threshold is not None else default_similarity_threshold()

    try:
        await repo.backfill_missing_embeddings(user_id=user_filter, limit=100)
        return await repo.find_similar_incidents(
            text=text,
            user_id=user_filter,
            limit=limit,
            threshold=effective_threshold,
            exclude_result_id=exclude_result_id,
            exclude_incident_id=exclude_incident_id,
        )
    except Exception as exc:
        logger.error("[API] similar incidents error: %s", exc)
        raise HTTPException(status_code=500, detail="Ошибка поиска похожих инцидентов") from exc


@router.post(
    "/incidents/similar",
    response_model=list[SimilarIncident],
    summary="Найти похожие прошлые инциденты по тексту (текст в теле запроса)",
)
async def find_similar_incidents_post(
    request: SimilarIncidentsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[SimilarIncident]:
    return await _do_find_similar(
        db,
        current_user,
        text=request.text,
        limit=request.limit,
        threshold=request.threshold,
        exclude_result_id=request.exclude_result_id,
        exclude_incident_id=request.exclude_incident_id,
    )


@router.get(
    "/incidents/similar",
    response_model=list[SimilarIncident],
    summary="Найти похожие прошлые инциденты по тексту (deprecated: используйте POST)",
    deprecated=True,
)
async def find_similar_incidents(
    db: DbSession,
    current_user: CurrentUser,
    text: str = Query(..., min_length=3, max_length=5000, description="Текст нового инцидента"),
    limit: int = Query(5, ge=1, le=20),
    threshold: float | None = Query(
        None, ge=0.0, le=1.0,
        description="Порог похожести; если не задан — подбирается под провайдер эмбеддингов",
    ),
    exclude_result_id: str | None = Query(None),
    exclude_incident_id: str | None = Query(None),
) -> list[SimilarIncident]:
    """Старый GET-вариант: оставлен для обратной совместимости (короткие тексты)."""
    return await _do_find_similar(
        db,
        current_user,
        text=text,
        limit=limit,
        threshold=threshold,
        exclude_result_id=exclude_result_id,
        exclude_incident_id=exclude_incident_id,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/results/compare
# ---------------------------------------------------------------------------

@router.get(
    "/results/compare",
    response_model=ComparisonResult,
    summary="Сравнение результатов нескольких методологий по incident_id",
)
async def compare_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: str = Query(..., description="ID инцидента для сравнения"),
) -> ComparisonResult:
    repo = RCARepository(db)
    user_filter = None if current_user.role == "admin" else current_user.user_id
    results = await repo.list_results(
        user_id=user_filter,
        incident_id=incident_id,
        limit=10,
        offset=0,
    )
    if not results:
        raise HTTPException(status_code=404, detail=f"Нет результатов для incident_id={incident_id}")

    for r in results:
        _check_owner_or_admin(r, current_user)

    try:
        comparison = _service.compare(results)
    except Exception as exc:
        logger.error("[API] compare error: %s", exc)
        raise HTTPException(status_code=500, detail="Ошибка при сравнении") from exc

    return comparison


# ---------------------------------------------------------------------------
# GET /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.get(
    "/results/{result_id}",
    response_model=RCAResult,
    summary="Получить результат анализа из БД",
)
async def get_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
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
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    _check_owner_or_admin(result, current_user)
    await repo.delete_result(result_id)


# ---------------------------------------------------------------------------
# PATCH /api/v1/results/{result_id}/recommendations/{rec_id}
# ---------------------------------------------------------------------------

class StatusUpdate(BaseModel):
    status: str


@router.patch(
    "/results/{result_id}/recommendations/{rec_id}",
    summary="Обновить статус рекомендации",
)
async def update_recommendation(
    result_id: str,
    rec_id: str,
    body: StatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    valid_statuses = {"open", "in_progress", "closed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Статус должен быть: {valid_statuses}")

    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    _check_owner_or_admin(result, current_user)

    updated = await repo.update_recommendation_status(result_id, rec_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена.")
    return {"result_id": result_id, "rec_id": rec_id, "status": body.status}
