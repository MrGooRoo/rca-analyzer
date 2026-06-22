"""
Оркестратор анализа корневых причин.

Поток:
  AnalysisRequest
      → PromptRenderer (Jinja2 → system + user prompt)
      → OpenRouterClient (LLM вызов с retry)
      → MethodologyRunner (raw dict → RCAResult)
      → RCAResult
Примечание по жизненному циклу httpx:
    OpenRouterClient создаётся свежим на каждый запрос (async with),
    чтобы избежать повторного использования закрытого httpx.AsyncClient.
Примечание по analyze_multi:
    Методологии запускаются параллельно через asyncio.gather,
    что сокращает общее время до длительности самой медленной методологии.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from difflib import SequenceMatcher
from typing import cast

from src.domain.methodologies import METHODOLOGY_NAMES_RU
from src.domain.methodologies.base import MethodologyRunner
from src.domain.methodologies.bowtie import BowTieRunner
from src.domain.methodologies.five_why import FiveWhyRunner
from src.domain.methodologies.fta import FaultTreeRunner
from src.domain.methodologies.ishikawa import IshikawaRunner
from src.domain.methodologies.rca_systemic import RcaSystemicRunner
from src.domain.models import (
    AnalysisRequest,
    ComparisonResult,
    LLMResponseValidationError,
    LLMSettings,
    MethodologyFailure,
    MethodologyNotSupportedError,
    MethodologyType,
    MultiAnalysisRequest,
    MultiAnalysisResponse,
    RCAResult,
    Recommendation,
)
from src.integrations.llm.openrouter import OpenRouterClient
from src.services.llm_conductor import LLMConductor
from src.services.prompt_renderer import PromptRenderer

logger = logging.getLogger(__name__)

_RUNNERS: dict[MethodologyType, MethodologyRunner] = {
    MethodologyType.FIVE_WHY:     FiveWhyRunner(),
    MethodologyType.ISHIKAWA:     IshikawaRunner(),
    MethodologyType.RCA_SYSTEMIC: RcaSystemicRunner(),
    MethodologyType.FTA:          FaultTreeRunner(),
    MethodologyType.BOWTIE:       BowTieRunner(),
}

# Порог подобия текстов для поиска «общих» причин/рекомендаций
_SIMILARITY_THRESHOLD = 0.55


def _texts_are_similar(a: str, b: str, threshold: float = _SIMILARITY_THRESHOLD) -> bool:
    """Определяет, достаточно ли похожи две строки (нечёткое сравнение)."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio() >= threshold


def _deduplicate_results(results: list[RCAResult]) -> list[RCAResult]:
    """
    Оставить только по одному результату на методологию — новейший по created_at.
    Это защищает compare() от повторных запусков одного инцидента.
    """
    seen: dict[str, RCAResult] = {}
    for r in sorted(results, key=lambda x: x.created_at or "", reverse=True):
        key = r.methodology.value
        if key not in seen:
            seen[key] = r
    # Сохраняем порядок оригинального списка по method
    original_order = list(dict.fromkeys(r.methodology.value for r in results))
    return [seen[k] for k in original_order if k in seen]


def _sanitize_error(exc: Exception) -> str:
    """Безопасное сообщение об ошибке для внешнего API (без traceback)."""
    message = str(exc)
    if len(message) > 200:
        return message[:200] + "..."
    return message or "Неизвестная ошибка"


class AnalysisService:
    """
    Сервис анализа инцидентов.

    llm_client используется как фабрика: при None каждый вызов analyze()
    создаёт новый OpenRouterClient. При передаче готового клиента
    (например, в тестах) он будет использован напрямую.
    """

    def __init__(
        self,
        llm_client:      OpenRouterClient | None = None,
        prompt_renderer: PromptRenderer | None   = None,
    ) -> None:
        self._llm_factory = (lambda *_, **__: llm_client) if llm_client else OpenRouterClient
        self._prompts     = prompt_renderer or PromptRenderer()

    _STAGE_LABELS: dict[str, str] = {
        "preparing": "Подготовка промпта",
        "llm":       "Ожидание ответа от модели",
        "parsing":   "Обработка результата",
    }

    async def analyze(
        self,
        request: AnalysisRequest,
        llm_settings: LLMSettings | None = None,
    ) -> RCAResult:
        runner = self._get_runner(request.methodology)

        logger.info(
            "[AnalysisService] Старт | methodology=%s severity=%s conductor=%s",
            request.methodology,
            request.incident.severity,
            bool(llm_settings),
        )

        if llm_settings is not None:
            result = await LLMConductor(
                llm_settings,
                llm_factory=self._llm_factory,
                prompt_renderer=self._prompts,
            ).analyze(request, runner)
        else:
            system_prompt, user_prompt = self._prompts.render(
                template_name=runner.get_prompt_template_name(),
                request=request,
            )

            async with self._llm_factory() as client:
                raw = await client.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

            result = await runner.run(request, raw)

        logger.info(
            "[AnalysisService] Готово | result_id=%s causes=%d recs=%d",
            result.result_id,
            len(result.causal_tree),
            len(result.recommendations),
        )

        return result

    async def analyze_stream(
        self,
        request: AnalysisRequest,
        llm_settings: LLMSettings | None = None,
    ):
        """
        SSE-генератор одиночного анализа.

        События:
          {"status": "started", "methodology": "five_why", "name": "5 Почему"}
          {"status": "stage", "stage": "preparing", "percent": 10, "message": "..."}
          {"status": "stage", "stage": "llm",       "percent": 40, "message": "..."}
          {"status": "stage", "stage": "parsing",   "percent": 80, "message": "..."}
          {"status": "done", "result": <RCAResult>}
          {"status": "error", "message": "...", "code": 400|502|500}
        """
        methodology_value = getattr(request.methodology, "value", request.methodology)
        ru_name = METHODOLOGY_NAMES_RU.get(methodology_value, methodology_value)
        yield {"status": "started", "methodology": methodology_value, "name": ru_name}

        try:
            runner = self._get_runner(request.methodology)
            yield {
                "status": "stage",
                "stage": "preparing",
                "percent": 10,
                "message": self._STAGE_LABELS["preparing"],
            }

            yield {
                "status": "stage",
                "stage": "llm",
                "percent": 40,
                "message": (
                    "Черновой анализ и верификация при необходимости"
                    if llm_settings is not None else self._STAGE_LABELS["llm"]
                ),
            }

            if llm_settings is not None:
                result = await LLMConductor(
                    llm_settings,
                    llm_factory=self._llm_factory,
                    prompt_renderer=self._prompts,
                ).analyze(request, runner)
            else:
                system_prompt, user_prompt = self._prompts.render(
                    template_name=runner.get_prompt_template_name(),
                    request=request,
                )

                async with self._llm_factory() as client:
                    raw = await client.complete(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    )

                result = await runner.run(request, raw)

            yield {
                "status": "stage",
                "stage": "parsing",
                "percent": 80,
                "message": self._STAGE_LABELS["parsing"],
            }
            logger.info(
                "[AnalysisService] analyze_stream готово | result_id=%s methodology=%s",
                result.result_id,
                methodology_value,
            )
            yield {"status": "done", "result": result}

        except MethodologyNotSupportedError as exc:
            logger.warning("[AnalysisService] analyze_stream unsupported: %s", exc)
            yield {"status": "error", "message": str(exc), "code": 400}
        except LLMResponseValidationError as exc:
            logger.error("[AnalysisService] analyze_stream LLM error: %s", exc)
            yield {
                "status": "error",
                "message": "LLM не вернул валидный ответ. Попробуйте ещё раз.",
                "code": 502,
            }
        except Exception as exc:
            logger.error("[AnalysisService] analyze_stream unexpected error: %s", exc)
            yield {"status": "error", "message": "Внутренняя ошибка сервера", "code": 500}

    @staticmethod
    def _get_runner(methodology: MethodologyType) -> MethodologyRunner:
        runner = _RUNNERS.get(methodology)
        if runner is None:
            raise MethodologyNotSupportedError(
                f"Методика '{methodology}' ещё не реализована. "
                f"Доступны: {list(_RUNNERS.keys())}"
            )
        return runner

    @classmethod
    def supported_methodologies(cls) -> list[MethodologyType]:
        return list(_RUNNERS.keys())

    async def analyze_multi(
        self,
        request: MultiAnalysisRequest,
        llm_settings: LLMSettings | None = None,
    ) -> MultiAnalysisResponse:
        incident_id = str(uuid.uuid4())

        single_requests = [
            AnalysisRequest(
                methodology=methodology,
                language=request.language,
                detail_level=request.detail_level,
                incident=request.incident,
            )
            for methodology in request.methodologies
        ]

        logger.info(
            "[AnalysisService] analyze_multi: запуск %d методологий параллельно: %s",
            len(single_requests),
            [r.methodology.value for r in single_requests],
        )

        gathered = await asyncio.gather(
            *[self.analyze(r, llm_settings=llm_settings) for r in single_requests],
            return_exceptions=True,
        )

        results: list[RCAResult] = []
        failures: list[MethodologyFailure] = []
        for req, item in zip(single_requests, gathered, strict=True):
            if isinstance(item, Exception):
                logger.error(
                    "[AnalysisService] Ошибка методики %s в analyze_multi: %s",
                    req.methodology.value, item,
                )
                failures.append(MethodologyFailure(
                    methodology=req.methodology,
                    error=_sanitize_error(item),
                ))
            else:
                results.append(cast(RCAResult, item))

        for result in results:
            result.incident_id = incident_id

        return MultiAnalysisResponse(results=results, failures=failures)

    # ------------------------------------------------------------------
    # Сравнение результатов (улучшенная эвристика)
    # ------------------------------------------------------------------

    @staticmethod
    def compare(results: list[RCAResult]) -> ComparisonResult:
        """
        Сравнить результаты анализа несколькими методиками.

        Алгоритм:
        0. Дедупликация: оставить по одному результату на методологию (новейший).
        1. Собрать все причины и рекомендации из каждого результата.
        2. Найти «общие» причины — те, что встречаются в ≥2 методиках
           с порогом текстового подобия ≥0.55.
        3. Оставшиеся причины — «различающиеся» (уникальные для методики).
        4. Найти общие рекомендации аналогичным образом.
        5. Сформировать итоговую сводку.
        """
        if not results:
            raise ValueError("Нет результатов для сравнения")

        # Дедупликация: один результат на методологию
        deduped = _deduplicate_results(results)

        if len(deduped) < 2:
            raise ValueError("Для сравнения нужно минимум 2 различных методики")

        incident_id = deduped[0].incident_id

        common_recs = AnalysisService._find_common_recommendations(deduped)
        differing_causes = AnalysisService._find_differing_causes(deduped)
        summary = AnalysisService._build_summary(deduped, common_recs, differing_causes)

        return ComparisonResult(
            incident_id=incident_id,
            results=deduped,
            common_recommendations=common_recs,
            differing_causes=differing_causes,
            summary=summary,
        )

    # ---- вспомогательные методы compare ----

    @staticmethod
    def _all_cause_texts(result: RCAResult) -> list[str]:
        """Собрать тексты всех причин (root + contributing + immediate)."""
        texts: list[str] = []
        for node in result.root_causes + result.contributing_causes + result.immediate_causes:
            texts.append(node.text)
        return texts

    @staticmethod
    def _find_common_recommendations(results: list[RCAResult]) -> list[Recommendation]:
        """
        Найти рекомендации, встречающиеся в ≥2 методиках.
        Каждая «общая» рекомендация представлена один раз (из первого совпадения).
        """
        all_recs_by_meth: dict[str, list[Recommendation]] = {}
        for r in results:
            key = r.methodology.value
            all_recs_by_meth[key] = r.recommendations

        meth_keys = list(all_recs_by_meth.keys())
        common: list[Recommendation] = []
        matched: set[tuple[int, int]] = set()

        for i in range(len(meth_keys)):
            for ri, rec_a in enumerate(all_recs_by_meth[meth_keys[i]]):
                if (i, ri) in matched:
                    continue
                found_in = {i}
                for j in range(i + 1, len(meth_keys)):
                    for rj, rec_b in enumerate(all_recs_by_meth[meth_keys[j]]):
                        if (j, rj) in matched:
                            continue
                        if _texts_are_similar(rec_a.text, rec_b.text):
                            found_in.add(j)
                            matched.add((j, rj))
                            break
                if len(found_in) >= 2:
                    common.append(rec_a)
                    matched.add((i, ri))

        return common

    @staticmethod
    def _find_differing_causes(results: list[RCAResult]) -> dict[str, list[str]]:
        """
        Найти причины, уникальные для каждой методики
        (т.е. не имеющие похожих в других методиках).
        """
        cause_texts_by_meth: dict[str, list[str]] = {}
        for r in results:
            key = r.methodology.value
            cause_texts_by_meth[key] = AnalysisService._all_cause_texts(r)

        meth_keys = list(cause_texts_by_meth.keys())
        differing: dict[str, list[str]] = {}

        for i, meth_a in enumerate(meth_keys):
            unique: list[str] = []
            for text_a in cause_texts_by_meth[meth_a]:
                is_common = False
                for j, meth_b in enumerate(meth_keys):
                    if i == j:
                        continue
                    for text_b in cause_texts_by_meth[meth_b]:
                        if _texts_are_similar(text_a, text_b):
                            is_common = True
                            break
                    if is_common:
                        break
                if not is_common:
                    unique.append(text_a)
            if unique:
                differing[meth_a] = unique

        return differing

    @staticmethod
    def _build_summary(
        results: list[RCAResult],
        common_recs: list[Recommendation],
        differing: dict[str, list[str]],
    ) -> str:
        """Построить текстовую сводку сравнения."""
        meth_names_ru = [
            METHODOLOGY_NAMES_RU.get(r.methodology.value, r.methodology.value)
            for r in results
        ]
        lines: list[str] = [
            f"Сравнение {len(results)} методик ({', '.join(meth_names_ru)}) по инциденту.",
        ]

        if common_recs:
            lines.append(
                f"Общие рекомендации ({len(common_recs)}): "
                + "; ".join(r.text[:80] for r in common_recs)
            )
        else:
            lines.append("Общих рекомендаций не найдено — методики дают независимые выводы.")

        total_unique = sum(len(v) for v in differing.values())
        if total_unique:
            diff_parts = ", ".join(
                f"{METHODOLOGY_NAMES_RU.get(k, k)}: {len(v)}"
                for k, v in differing.items()
            )
            lines.append(f"Уникальные причины: {total_unique} ({diff_parts}).")
        else:
            lines.append("Все причины пересекаются между методиками.")

        # Уровень уверенности читаемым текстом, не словарём Python
        conf_parts = ", ".join(
            f"{METHODOLOGY_NAMES_RU.get(r.methodology.value, r.methodology.value)}: {round(r.confidence_avg * 100)}%"
            for r in results
        )
        lines.append(f"Средняя уверенность: {conf_parts}.")

        return " ".join(lines)
