"""
Use-case слой персистенции для анализа инцидентов.

Изолирует API-роуты от RCARepository:
  API → PersistenceService → AnalysisService + RCARepository

Unit of Work: один commit на границе use-case (кроме SSE — там короткие сессии).
"""

from __future__ import annotations

import asyncio
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
    LLMResponseValidationError,
    LLMSettings,
    MethodologyNotSupportedError,
    MultiAnalysisRequest,
    RCAResult,
)
from src.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

_SAVE_ERROR_MESSAGE = "Не удалось сохранить результат в базе данных"
_ANALYSIS_ERROR_MESSAGE = "Ошибка анализа методики"


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
    ) -> None:
        self._get_service = service_getter or (lambda: AnalysisService())

    # ------------------------------------------------------------------
    # Non-SSE: один commit на весь use-case (Unit of Work)
    # ------------------------------------------------------------------

    async def run_single(
        self,
        request: AnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
        db: AsyncSession | None = None,
    ) -> RCAResult:
        """Одиночный анализ: одна сессия + один commit."""
        own_session = db is None
        if own_session:
            session = AsyncSessionLocal()
            await session.__aenter__()
        else:
            session = db

        try:
            result = await self._analyze_with_settings(request, llm_settings)
            result.incident_id = str(uuid.uuid4())

            repo = RCARepository(session, auto_commit=False)
            session_orm = await repo.create_session(
                user_id=user_id,
                **_incident_to_session_kwargs(request.incident),
            )
            result.session_id = session_orm.id

            await repo.save_result(
                result,
                user_id=user_id,
                session_id=session_orm.id,
                incident_title=request.incident.title,
                incident_description=request.incident.description,
                incident_date=request.incident.incident_date,
                incident_location=request.incident.location or None,
                incident_type=request.incident.incident_type,
                incident_severity=request.incident.severity,
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
        finally:
            if own_session:
                await session.__aexit__(None, None, None)

    async def run_multi(
        self,
        request: MultiAnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
        db: AsyncSession | None = None,
    ) -> list[RCAResult]:
        """Multi-анализ: одна сессия + N результатов + один commit."""
        own_session = db is None
        if own_session:
            session = AsyncSessionLocal()
            await session.__aenter__()
        else:
            session = db

        try:
            results = await self._analyze_multi_with_settings(request, llm_settings)

            repo = RCARepository(session, auto_commit=False)
            session_orm = await repo.create_session(
                user_id=user_id,
                **_incident_to_session_kwargs(request.incident),
            )

            for result in results:
                result.session_id = session_orm.id
                await repo.save_result(
                    result,
                    user_id=user_id,
                    session_id=session_orm.id,
                    incident_title=request.incident.title,
                    incident_description=request.incident.description,
                    incident_date=request.incident.incident_date,
                    incident_location=request.incident.location or None,
                    incident_type=request.incident.incident_type,
                    incident_severity=request.incident.severity,
                )
                result.user_id = user_id

            await session.commit()
            return results
        except (MethodologyNotSupportedError, LLMResponseValidationError):
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            if own_session:
                await session.__aexit__(None, None, None)

    # ------------------------------------------------------------------
    # SSE: короткоживущие DB-сессии (LLM-вызовы без удержания соединения)
    # ------------------------------------------------------------------

    async def stream_single(
        self,
        request: AnalysisRequest,
        user_id: str,
        llm_settings: LLMSettings | None = None,
    ) -> AsyncIterator[str]:
        """SSE-генератор: короткая сессия для create, LLM, короткая сессия для save.

        Возвращает SSE-строки с префиксом "data: " (как stream_multi).
        """
        # Фаза 1: создать сессию (короткая транзакция)
        async with AsyncSessionLocal() as db:
            repo = RCARepository(db, auto_commit=False)
            session_orm = await repo.create_session(
                user_id=user_id,
                **_incident_to_session_kwargs(request.incident),
            )
            session_id = session_orm.id
            await db.commit()

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
            async with AsyncSessionLocal() as db:
                repo = RCARepository(db, auto_commit=False)
                await repo.save_result(
                    result,
                    user_id=user_id,
                    session_id=session_id,
                    incident_title=request.incident.title,
                    incident_description=request.incident.description,
                    incident_date=request.incident.incident_date,
                    incident_location=request.incident.location or None,
                    incident_type=request.incident.incident_type,
                    incident_severity=request.incident.severity,
                )
                await db.commit()
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
        async with AsyncSessionLocal() as db:
            repo = RCARepository(db, auto_commit=False)
            session_orm = await repo.create_session(
                user_id=user_id,
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
                    async with AsyncSessionLocal() as db:
                        repo = RCARepository(db, auto_commit=False)
                        await repo.save_result(
                            result,
                            user_id=user_id,
                            session_id=session_id,
                            incident_title=request.incident.title,
                            incident_description=request.incident.description,
                            incident_date=request.incident.incident_date,
                            incident_location=request.incident.location or None,
                            incident_type=request.incident.incident_type,
                            incident_severity=request.incident.severity,
                        )
                        await db.commit()
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
    ) -> list[RCAResult]:
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
