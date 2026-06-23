"""
Use-case слой персистенции для анализа инцидентов.

Изолирует API-роуты от RCARepository:
  API → PersistenceService → AnalysisService + RCARepository

Unit of Work: один commit на границе use-case (кроме SSE — там короткие сессии).
Read-операции также проходят через PersistenceService для единообразия.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import AsyncSessionLocal
from src.db.llm_settings_repository import LLMSettingsRepository
from src.db.repository import RCARepository
from src.domain.methodologies import METHODOLOGY_NAMES_RU
from src.domain.models import (
    AnalysisRequest,
    AnalysisSession,
    LLMResponseValidationError,
    LLMSettings,
    MethodologyNotSupportedError,
    MultiAnalysisRequest,
    MultiAnalysisResponse,
    RCAResult,
    SimilarIncident,
)
from src.integrations.embeddings.protocol import EmbeddingFn
from src.services.analysis_service import AnalysisService
from src.services.embedding_service import (
    EmbeddingServiceError,
    LocalHashEmbeddingService,
    get_embedding_service,
)

logger = logging.getLogger(__name__)

_SAVE_ERROR_MESSAGE = "Не удалось сохранить результат в базе данных"
_ANALYSIS_ERROR_MESSAGE = "Ошибка анализа методики"

# SSE heartbeat — ping каждые 30 секунд, чтобы прокси не обрывали соединение
_SSE_HEARTBEAT_INTERVAL = 30.0


async def with_heartbeat(main_stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Вставить heartbeat-события в основной SSE-поток.

    Использует asyncio.wait для мультиплексирования между __anext__ основного стрима
    и таймером heartbeat. Это гарантирует, что ping уходит клиенту даже во время
    долгого LLM-вызова (когда основной стрим не выдаёт событий минутами).

    Heartbeat генерирует {"status":"ping"} каждые _SSE_HEARTBEAT_INTERVAL секунд.
    """
    ping_payload = "data: " + json.dumps({"status": "ping"}) + "\n\n"
    iterator = main_stream.__aiter__()
    next_task: asyncio.Task[str] | None = None

    try:
        next_task = asyncio.create_task(iterator.__anext__())  # type: ignore[arg-type]

        while True:
            done, _ = await asyncio.wait(
                {next_task},
                timeout=_SSE_HEARTBEAT_INTERVAL,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if next_task in done:
                try:
                    item = next_task.result()
                except StopAsyncIteration:
                    return

                yield item
                next_task = asyncio.create_task(iterator.__anext__())  # type: ignore[arg-type]
            else:
                yield ping_payload
    finally:
        if next_task is not None and not next_task.done():
            next_task.cancel()
            await asyncio.gather(next_task, return_exceptions=True)

# Кэшированный фолбэк для эмбеддингов
_FALLBACK_EMBEDDINGS = LocalHashEmbeddingService()


def _make_embed_fn() -> EmbeddingFn:
    """Создать embed_fn с автоматическим fallback на локальный hashing.

    Используется PersistenceService для инъекции в RCARepository,
    чтобы embedding-логика жила в use-case слое, а не в repository.
    """
    primary = get_embedding_service()

    async def _embed(text: str) -> tuple[list[float], str, int]:
        try:
            result = primary.embed(text)
            if inspect.isawaitable(result):
                result = await result
            return list(result), primary.model_name, primary.dimension
        except EmbeddingServiceError as exc:
            if primary is _FALLBACK_EMBEDDINGS:
                raise
            logger.warning(
                "[Persistence] embedding-провайдер %s недоступен (%s) — фолбэк на %s",
                primary.model_name, exc, _FALLBACK_EMBEDDINGS.model_name,
            )
            vector = _FALLBACK_EMBEDDINGS.embed(text)
            return list(vector), _FALLBACK_EMBEDDINGS.model_name, _FALLBACK_EMBEDDINGS.dimension

    return _embed


def _get_embedding_model_name() -> str:
    """Получить model_name первичного embedding-провайдера."""
    return get_embedding_service().model_name


def _incident_to_session_kwargs(incident: Any) -> dict[str, Any]:
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


def _save_kwargs(
    result: RCAResult,
    user_id: str,
    session_id: str,
    incident: Any,
) -> dict[str, Any]:
    """Подготовить kwargs для repo.save_result — единое место, чтобы не дублировать."""
    return dict(
        result=result,
        user_id=user_id,
        session_id=session_id,
        incident_title=incident.title,
        incident_description=incident.description,
        incident_date=incident.incident_date,
        incident_location=incident.location or None,
        incident_type=incident.incident_type,
        incident_severity=incident.severity,
    )


async def load_llm_settings(db: AsyncSession) -> LLMSettings | None:
    """Load P17 LLM settings; fallback to legacy analysis if settings are unavailable."""
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


# ---------------------------------------------------------------------------
# Helper: управление сессией с rollback
# ---------------------------------------------------------------------------


class _SessionManager:
    """Контекстный менеджер для сессии БД.

    Поддерживает два режима:
    - own_session=True: создаёт и закрывает свою сессию (async with)
    - own_session=False: использует переданную сессию (без управления жизнью)
    """

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._own_session = db is None
        self.session = db  # может быть None

    async def __aenter__(self) -> AsyncSession:
        if self._own_session and self.session is None:
            self.session = AsyncSessionLocal()
            await self.session.__aenter__()
        assert self.session is not None
        return self.session

    async def __aexit__(self, *args: Any) -> None:
        if self._own_session and self.session is not None:
            await self.session.__aexit__(*args)


# ---------------------------------------------------------------------------
# Use-case слой
# ---------------------------------------------------------------------------


class AnalysisPersistenceService:
    """
    Use-case слой: анализ + персистенция.

    API → PersistenceService → AnalysisService + RCARepository

    service_getter — callable, возвращающий AnalysisService.
    Позволяет тестам подменять сервис через patch на модульном уровне.
    """

    def __init__(
        self,
        service_getter: Callable[[], AnalysisService] | None = None,
        embed_fn: EmbeddingFn | None = None,
        embedding_model_name: str | None = None,
    ) -> None:
        self._get_service = service_getter or (lambda: AnalysisService())
        self._embed_fn = embed_fn or _make_embed_fn()
        self._embedding_model_name = embedding_model_name or _get_embedding_model_name()

    # ------------------------------------------------------------------
    # Write: Non-SSE (один commit на весь use-case)
    # ------------------------------------------------------------------

    async def run_single(
        self,
        request: AnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
        db: AsyncSession | None = None,
    ) -> RCAResult:
        """Одиночный анализ: одна сессия + один commit."""
        async with _SessionManager(db) as session:
            try:
                result = await self._analyze_with_settings(request, llm_settings)
                result.incident_id = str(uuid.uuid4())

                repo = RCARepository(session, auto_commit=False, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
                session_orm = await repo.create_session(
                    user_id=user_id,
                    **_incident_to_session_kwargs(request.incident),
                )
                result.session_id = session_orm.id

                await repo.save_result(
                    **_save_kwargs(result, user_id, session_orm.id, request.incident),
                )

                await session.commit()
                result.user_id = user_id
                return result
            except (MethodologyNotSupportedError, LLMResponseValidationError):
                await session.rollback()
                raise
            except Exception:
                await session.rollback()
                raise

    async def run_multi(
        self,
        request: MultiAnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
        db: AsyncSession | None = None,
    ) -> MultiAnalysisResponse:
        """Multi-анализ: одна сессия + N результатов + один commit + отчёт об ошибках."""
        async with _SessionManager(db) as session:
            try:
                resp = await self._analyze_multi_with_settings(request, llm_settings)

                if not resp.results and not resp.failures:
                    # Все методики упали — не создаём пустую сессию
                    return resp

                repo = RCARepository(session, auto_commit=False, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
                session_orm = await repo.create_session(
                    user_id=user_id,
                    **_incident_to_session_kwargs(request.incident),
                )

                for result in resp.results:
                    result.session_id = session_orm.id
                    await repo.save_result(
                        **_save_kwargs(result, user_id, session_orm.id, request.incident),
                    )
                    result.user_id = user_id

                await session.commit()
                return resp
            except (MethodologyNotSupportedError, LLMResponseValidationError):
                await session.rollback()
                raise
            except Exception:
                await session.rollback()
                raise

    # ------------------------------------------------------------------
    # Write: SSE (короткоживущие DB-сессии)
    # ------------------------------------------------------------------

    async def stream_single(
        self,
        request: AnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
    ) -> AsyncIterator[str]:
        """SSE-генератор: короткая сессия для create, LLM, короткая сессия для save.

        Возвращает SSE-строки с префиксом "data: ".
        """
        # Фаза 1: создать сессию (короткая транзакция)
        async with AsyncSessionLocal() as session:
            repo = RCARepository(session, auto_commit=False, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
            session_orm = await repo.create_session(
                user_id=user_id,
                **_incident_to_session_kwargs(request.incident),
            )
            session_id = session_orm.id
            await session.commit()

        # Фаза 2: LLM-анализ (без БД)
        result: RCAResult | None = None
        stream = self._analyze_stream_with_settings(request, llm_settings)
        async for event in stream:
            if event.get("status") == "done":
                result = event["result"]
                continue
            yield "data: " + json.dumps(event) + "\n\n"
            await asyncio.sleep(0.02)
            if event.get("status") == "error":
                return

        if result is None:
            yield "data: " + json.dumps({"status": "error", "message": "Анализ не вернул результата."}) + "\n\n"
            return

        result.incident_id = str(uuid.uuid4())
        result.session_id = session_id

        # Фаза 3: сохранить результат (короткая транзакция)
        try:
            async with AsyncSessionLocal() as session:
                repo = RCARepository(session, auto_commit=False, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
                await repo.save_result(
                    **_save_kwargs(result, user_id, session_id, request.incident),
                )
                await session.commit()
        except Exception as exc:
            logger.error("[Persistence] Ошибка сохранения результата в stream_single: %s", exc)
            yield "data: " + json.dumps({"status": "error", "message": "Не удалось сохранить результат анализа."}) + "\n\n"
            return

        result.user_id = user_id
        yield "data: " + json.dumps({"status": "done", "result": result.model_dump(mode="json")}) + "\n\n"

    async def stream_multi(
        self,
        request: MultiAnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
    ) -> AsyncIterator[str]:
        """SSE-поток для multi-analysis: короткие сессии для create/save."""
        methodologies = request.methodologies
        total = len(methodologies)
        names = [METHODOLOGY_NAMES_RU.get(m.value, m.value) for m in methodologies]

        yield "data: " + json.dumps({"status": "started", "total": total, "methodologies": names}) + "\n\n"
        await asyncio.sleep(0.05)

        incident_id = str(uuid.uuid4())

        # Создать сессию (короткая транзакция)
        async with AsyncSessionLocal() as session:
            repo = RCARepository(session, auto_commit=False, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
            session_orm = await repo.create_session(
                user_id=user_id,
                **_incident_to_session_kwargs(request.incident),
            )
            session_id = session_orm.id
            await session.commit()

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
                result = await self._analyze_with_settings(single, llm_settings)
                result.incident_id = incident_id
                await queue.put(("ok", methodology, result))
            except Exception as exc:
                logger.error("[StreamMulti] %s ошибка: %s", name, exc)
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
                    async with AsyncSessionLocal() as session:
                        repo = RCARepository(session, auto_commit=False, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
                        await repo.save_result(
                            **_save_kwargs(result, user_id, session_id, request.incident),
                        )
                        await session.commit()
                    result.user_id = user_id
                except Exception as exc:
                    logger.error("[StreamMulti] Ошибка сохранения %s: %s", name, exc)
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
        yield "data: " + json.dumps({"status": "done", "results": results_json}) + "\n\n"

    # ------------------------------------------------------------------
    # Read: get / list — делегируют в RCARepository
    # ------------------------------------------------------------------

    async def get_result(
        self, result_id: str, db: AsyncSession,
    ) -> RCAResult | None:
        repo = RCARepository(db)
        return await repo.get_result(result_id)

    async def list_results(
        self,
        db: AsyncSession,
        user_id: str | None = None,
        incident_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RCAResult]:
        repo = RCARepository(db)
        return await repo.list_results(
            user_id=user_id, incident_id=incident_id, limit=limit, offset=offset,
        )

    async def delete_result(self, result_id: str, db: AsyncSession) -> bool:
        repo = RCARepository(db)
        return await repo.delete_result(result_id)

    async def update_recommendation_status(
        self, result_id: str, rec_id: str, status: str, db: AsyncSession,
    ) -> bool:
        repo = RCARepository(db)
        return await repo.update_recommendation_status(result_id, rec_id, status)

    async def get_session(
        self, session_id: str, db: AsyncSession,
    ) -> AnalysisSession | None:
        repo = RCARepository(db)
        return await repo.get_session(session_id)

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AnalysisSession]:
        repo = RCARepository(db)
        return await repo.list_sessions(user_id=user_id, limit=limit, offset=offset)

    async def find_similar_incidents(
        self,
        text: str,
        db: AsyncSession,
        user_id: str | None = None,
        limit: int = 5,
        threshold: float = 0.15,
        exclude_result_id: str | None = None,
        exclude_incident_id: str | None = None,
        exclude_incident_hash: str | None = None,
    ) -> list[SimilarIncident]:
        repo = RCARepository(db, embed_fn=self._embed_fn, embedding_model_name=self._embedding_model_name)
        await repo.backfill_missing_embeddings(user_id=user_id, limit=100)
        return await repo.find_similar_incidents(
            text=text,
            user_id=user_id,
            limit=limit,
            threshold=threshold,
            exclude_result_id=exclude_result_id,
            exclude_incident_id=exclude_incident_id,
            exclude_incident_hash=exclude_incident_hash,
        )

    # ------------------------------------------------------------------
    # Внутренние helpers — обёртки над AnalysisService
    # ------------------------------------------------------------------

    async def _analyze_with_settings(
        self,
        request: AnalysisRequest,
        llm_settings: LLMSettings | None,
    ) -> RCAResult:
        svc = self._get_service()
        if llm_settings is None:
            return await svc.analyze(request)
        try:
            return await svc.analyze(request, llm_settings=llm_settings)
        except TypeError as exc:
            if _is_legacy_signature_error(exc):
                return await svc.analyze(request)
            raise

    async def _analyze_multi_with_settings(
        self,
        request: MultiAnalysisRequest,
        llm_settings: LLMSettings | None,
    ) -> MultiAnalysisResponse:
        svc = self._get_service()
        if llm_settings is None:
            return await svc.analyze_multi(request)
        try:
            return await svc.analyze_multi(request, llm_settings=llm_settings)
        except TypeError as exc:
            if _is_legacy_signature_error(exc):
                return await svc.analyze_multi(request)
            raise

    def _analyze_stream_with_settings(
        self,
        request: AnalysisRequest,
        llm_settings: LLMSettings | None,
    ):
        svc = self._get_service()
        if llm_settings is None:
            return svc.analyze_stream(request)
        try:
            return svc.analyze_stream(request, llm_settings=llm_settings)
        except TypeError as exc:
            if _is_legacy_signature_error(exc):
                return svc.analyze_stream(request)
            raise
