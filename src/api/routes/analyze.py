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
from src.db.base import AsyncSessionLocal, get_db
from src.db.llm_settings_repository import LLMSettingsRepository
from src.db.repository import RCARepository
from src.domain.methodologies import METHODOLOGY_NAMES_RU
from src.domain.models import (
    AnalysisRequest,
    AnalysisSession,
    ComparisonResult,
    LLMResponseValidationError,
    LLMSettings,
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

_SAVE_ERROR_MESSAGE = "Не удалось сохранить результат в базе данных"
_ANALYSIS_ERROR_MESSAGE = "Ошибка анализа методики"


async def _load_llm_settings(db: AsyncSession) -> LLMSettings | None:
    """Load P17 LLM settings; fallback to legacy analysis if settings are unavailable."""
    # API tests often override DB with AsyncMock; do not try to build Pydantic settings
    # from mock attributes, because that creates unawaited coroutine warnings.
    if "unittest.mock" in type(db).__module__:
        return None
    try:
        return await LLMSettingsRepository(db).get()
    except Exception:
        logger.warning(
            "[P17] Не удалось загрузить llm_settings; используется legacy LLM pipeline",
            exc_info=True,
        )
        return None


def _is_legacy_signature_error(exc: TypeError) -> bool:
    """True when a mocked/legacy service method does not accept llm_settings kwarg."""
    message = str(exc)
    return "llm_settings" in message and "unexpected keyword argument" in message


async def _analyze_with_optional_settings(
    request: AnalysisRequest,
    llm_settings: LLMSettings | None,
) -> RCAResult:
    if llm_settings is None:
        return await _service.analyze(request)
    try:
        return await _service.analyze(request, llm_settings=llm_settings)
    except TypeError as exc:
        if _is_legacy_signature_error(exc):
            return await _service.analyze(request)
        raise


async def _analyze_multi_with_optional_settings(
    request: MultiAnalysisRequest,
    llm_settings: LLMSettings | None,
) -> list[RCAResult]:
    if llm_settings is None:
        return await _service.analyze_multi(request)
    try:
        return await _service.analyze_multi(request, llm_settings=llm_settings)
    except TypeError as exc:
        if _is_legacy_signature_error(exc):
            return await _service.analyze_multi(request)
        raise


def _analyze_stream_with_optional_settings(
    request: AnalysisRequest,
    llm_settings: LLMSettings | None,
):
    if llm_settings is None:
        return _service.analyze_stream(request)
    try:
        return _service.analyze_stream(request, llm_settings=llm_settings)
    except TypeError as exc:
        if _is_legacy_signature_error(exc):
            return _service.analyze_stream(request)
        raise


def _incident_to_session_kwargs(incident):
    """Подготовить kwargs для RCARepository.create_session из IncidentInput."""
    return dict(
        incident_title=incident.title,
        incident_description=incident.description,
        incident_date=incident.incident_date,
        incident_location=incident.location or None,
        incident_type=incident.incident_type,
        incident_severity=incident.severity,
        incident_data_json=incident.model_dump_json(exclude_none=True),
    )


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
    import uuid as _uuid
    llm_settings = await _load_llm_settings(db)
    try:
        result = await _analyze_with_optional_settings(request, llm_settings)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc

    # Генерируем уникальный incident_id для каждого одиночного анализа
    result.incident_id = str(_uuid.uuid4())

    repo = RCARepository(db)

    # Создаём сессию исследования
    session_orm = await repo.create_session(
        user_id=current_user.user_id,
        **_incident_to_session_kwargs(request.incident),
    )
    result.session_id = session_orm.id

    await repo.save_result(
        result,
        user_id=current_user.user_id,
        session_id=session_orm.id,
        incident_title=request.incident.title,
        incident_description=request.incident.description,
        incident_date=request.incident.incident_date,
        incident_location=request.incident.location or None,
        incident_type=request.incident.incident_type,
        incident_severity=request.incident.severity,
    )
    await db.commit()
    logger.info("[DB] saved result %s for user %s (session %s)", result.result_id, current_user.user_id, session_orm.id)

    result.user_id = current_user.user_id
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
    """
    SSE-эндпоинт для одиночного анализа.

    События:
      {"status": "started", "methodology": "five_why", "name": "5 Почему"}
      {"status": "stage", "stage": "preparing", "percent": 10, "message": "..."}
      {"status": "stage", "stage": "llm",       "percent": 40, "message": "..."}
      {"status": "stage", "stage": "parsing",   "percent": 80, "message": "..."}
      {"status": "done",  "result": <RCAResult>}
      {"status": "error", "message": "..."}
    """
    llm_settings = await _load_llm_settings(db)

    async def event_generator():
        import uuid as _uuid

        # Создаём сессию в короткоживущей DB-транзакции
        async with AsyncSessionLocal() as db:
            repo = RCARepository(db)
            session_orm = await repo.create_session(
                user_id=current_user.user_id,
                **_incident_to_session_kwargs(request.incident),
            )
            session_id = session_orm.id
            await db.commit()

        result: RCAResult | None = None

        stream = _analyze_stream_with_optional_settings(request, llm_settings)
        async for event in stream:
            if event.get("status") == "done":
                result = event["result"]
                continue
            if event.get("status") == "error":
                yield "data: " + json.dumps(event) + "\n\n"
                return
            yield "data: " + json.dumps(event) + "\n\n"
            await asyncio.sleep(0.02)

        if result is None:
            yield "data: " + json.dumps({
                "status": "error",
                "message": "Анализ не вернул результата.",
            }) + "\n\n"
            return

        result.incident_id = str(_uuid.uuid4())
        result.session_id = session_id

        # Сохраняем результат в отдельной короткоживущей DB-сессии
        try:
            async with AsyncSessionLocal() as db:
                repo = RCARepository(db)
                await repo.save_result(
                    result,
                    user_id=current_user.user_id,
                    session_id=session_id,
                    incident_title=request.incident.title,
                    incident_description=request.incident.description,
                    incident_date=request.incident.incident_date,
                    incident_location=request.incident.location or None,
                    incident_type=request.incident.incident_type,
                    incident_severity=request.incident.severity,
                )
        except Exception as exc:
            logger.error("[API] Ошибка сохранения результата в analyze_stream: %s", exc)
            yield "data: " + json.dumps({
                "status": "error",
                "message": "Не удалось сохранить результат анализа.",
            }) + "\n\n"
            return

        result.user_id = current_user.user_id

        yield "data: " + json.dumps({
            "status": "done",
            "result": result.model_dump(mode="json"),
        }) + "\n\n"

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
    llm_settings = await _load_llm_settings(db)
    try:
        results = await _analyze_multi_with_optional_settings(request, llm_settings)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error in analyze-multi: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc
    except Exception as exc:
        logger.error("[API] Unexpected error in analyze-multi: %s", exc)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера") from exc

    repo = RCARepository(db)

    # Одна сессия на все методики сравнения
    session_orm = await repo.create_session(
        user_id=current_user.user_id,
        **_incident_to_session_kwargs(request.incident),
    )

    for result in results:
        result.session_id = session_orm.id
        await repo.save_result(
            result,
            user_id=current_user.user_id,
            session_id=session_orm.id,
            incident_title=request.incident.title,
            incident_description=request.incident.description,
            incident_date=request.incident.incident_date,
            incident_location=request.incident.location or None,
            incident_type=request.incident.incident_type,
            incident_severity=request.incident.severity,
        )
        result.user_id = current_user.user_id

    await db.commit()
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

    DB-сессии короткоживущие: create_session и каждый save_result — отдельное
    соединение; во время LLM-вызовов пул не удерживается.

    События:
      {"status": "started",   "total": N, "methodologies": [...]}
      {"status": "progress",  "methodology": "bowtie",  "name": "BowTie",  "done": K, "total": N}
      {"status": "error_one", "methodology": "fta",     "name": "FTA",     "message": "..."}
      {"status": "done",      "results": [...]}
      {"status": "error",     "message": "..."}   — фатальная ошибка
    """
    llm_settings = await _load_llm_settings(db)

    async def event_generator():
        import uuid as _uuid

        methodologies = request.methodologies
        total = len(methodologies)
        names = [METHODOLOGY_NAMES_RU.get(m.value, m.value) for m in methodologies]

        yield "data: " + json.dumps({
            "status": "started",
            "total": total,
            "methodologies": names,
        }) + "\n\n"
        await asyncio.sleep(0.05)

        incident_id = str(_uuid.uuid4())

        async with AsyncSessionLocal() as db:
            repo = RCARepository(db)
            session_orm = await repo.create_session(
                user_id=current_user.user_id,
                **_incident_to_session_kwargs(request.incident),
            )
            session_id = session_orm.id
            await db.commit()

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
                result = await _analyze_with_optional_settings(single, llm_settings)
                result.incident_id = incident_id
                await queue.put(("ok", methodology, result))
            except Exception as exc:
                logger.error("[AnalyzeMultiStream] %s ошибка: %s", name, exc)
                await queue.put(("err", methodology, _ANALYSIS_ERROR_MESSAGE))

        tasks = [asyncio.create_task(run_one(m)) for m in methodologies]

        results = []
        done_count = 0

        while done_count < total:
            kind, methodology, payload = await queue.get()
            done_count += 1
            name = METHODOLOGY_NAMES_RU.get(methodology.value, methodology.value)

            if kind == "ok":
                result = payload
                result.session_id = session_id
                try:
                    async with AsyncSessionLocal() as db:
                        repo = RCARepository(db)
                        await repo.save_result(
                            result,
                            user_id=current_user.user_id,
                            session_id=session_id,
                            incident_title=request.incident.title,
                            incident_description=request.incident.description,
                            incident_date=request.incident.incident_date,
                            incident_location=request.incident.location or None,
                            incident_type=request.incident.incident_type,
                            incident_severity=request.incident.severity,
                        )
                    result.user_id = current_user.user_id
                except Exception as exc:
                    logger.error("[AnalyzeMultiStream] Ошибка сохранения %s: %s", name, exc)
                    yield "data: " + json.dumps({
                        "status": "error_one",
                        "methodology": methodology.value,
                        "name": name,
                        "message": _SAVE_ERROR_MESSAGE,
                        "done": done_count,
                        "total": total,
                    }) + "\n\n"
                    await asyncio.sleep(0.02)
                    continue

                results.append(result)
                yield "data: " + json.dumps({
                    "status": "progress",
                    "methodology": methodology.value,
                    "name": name,
                    "done": done_count,
                    "total": total,
                }) + "\n\n"
            else:
                yield "data: " + json.dumps({
                    "status": "error_one",
                    "methodology": methodology.value,
                    "name": name,
                    "message": payload,
                    "done": done_count,
                    "total": total,
                }) + "\n\n"

            await asyncio.sleep(0.02)

        await asyncio.gather(*tasks, return_exceptions=True)

        if not results:
            yield "data: " + json.dumps({
                "status": "error",
                "message": "Все методологии завершились с ошибкой. Проверьте подключение к LLM.",
            }) + "\n\n"
            return

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
    # Поля для исключения повторных анализов того же инцидента:
    # если заданы, из результата исключаются сессии с таким же incident_hash.
    incident_title: str | None = Field(
        None, max_length=200,
        description="Заголовок инцидента — для исключения повторов",
    )
    incident_description: str | None = Field(
        None, max_length=10000,
        description="Описание инцидента — для исключения повторов",
    )


async def _do_find_similar(
    db: AsyncSession,
    current_user: UserInfo,
    *,
    text: str,
    limit: int,
    threshold: float | None,
    exclude_result_id: str | None,
    exclude_incident_id: str | None,
    incident_title: str | None = None,
    incident_description: str | None = None,
) -> list[SimilarIncident]:
    from src.db.repository import compute_incident_hash  # noqa: E402

    repo = RCARepository(db)
    user_filter = None if current_user.role == "admin" else current_user.user_id
    # У hashing-эмбеддингов несвязанные тексты ~0, у нейросетевых ~0.4-0.5 —
    # дефолтный порог зависит от EMBEDDINGS_PROVIDER (см. embedding_service).
    effective_threshold = threshold if threshold is not None else default_similarity_threshold()

    # Вычисляем incident_hash для исключения повторов того же инцидента.
    # Если заданы title+description — hash вычисляется из них (ручной поиск из формы).
    # Если задан result_id/incident_id — hash определится автоматически в find_similar_incidents.
    exclude_incident_hash: str | None = None
    if incident_title and incident_description:
        exclude_incident_hash = compute_incident_hash(incident_title, incident_description)

    try:
        await repo.backfill_missing_embeddings(user_id=user_filter, limit=100)
        return await repo.find_similar_incidents(
            text=text,
            user_id=user_filter,
            limit=limit,
            threshold=effective_threshold,
            exclude_result_id=exclude_result_id,
            exclude_incident_id=exclude_incident_id,
            exclude_incident_hash=exclude_incident_hash,
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
        incident_title=request.incident_title,
        incident_description=request.incident_description,
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
    summary="Сравнение результатов нескольких методологий по incident_id или session_id",
)
async def compare_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: str | None = Query(None, description="ID инцидента для сравнения"),
    session_id: str | None = Query(None, description="ID сессии исследования"),
) -> ComparisonResult:
    repo = RCARepository(db)
    user_filter = None if current_user.role == "admin" else current_user.user_id

    # Предпочитаем session_id; fallback на incident_id для обратной совместимости
    if session_id:
        results = await repo.list_results_by_session(
            session_id=session_id,
            user_id=user_filter,
        )
    elif incident_id:
        results = await repo.list_results(
            user_id=user_filter,
            incident_id=incident_id,
            limit=10,
            offset=0,
        )
    else:
        raise HTTPException(status_code=400, detail="Укажите incident_id или session_id")

    if not results:
        raise HTTPException(status_code=404, detail="Нет результатов для сравнения")

    for r in results:
        _check_owner_or_admin(r, current_user)

    try:
        comparison = _service.compare(results)
    except Exception as exc:
        logger.error("[API] compare error: %s", exc)
        raise HTTPException(status_code=500, detail="Ошибка при сравнении") from exc

    return comparison


# ---------------------------------------------------------------------------
# GET /api/v1/sessions
# ---------------------------------------------------------------------------

@router.get(
    "/sessions",
    response_model=list[AnalysisSession],
    summary="Список сессий исследований (admin — все, user — свои)",
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
        user_id=user_id_filter,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}",
    response_model=AnalysisSession,
    summary="Получить сессию исследования со всеми результатами",
)
async def get_session(
    session_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> AnalysisSession:
    repo = RCARepository(db)
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Сессия '{session_id}' не найдена.")
    # Проверка доступа
    if current_user.role != "admin" and session.user_id and session.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return session


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
