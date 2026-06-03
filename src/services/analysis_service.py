"""
Оркестратор анализа корневых причин.

Поток:
  AnalysisRequest
      → PromptRenderer (Jinja2 → system + user prompt)
      → OpenRouterClient (LLM вызов с retry)
      → MethodologyRunner (raw dict → RCAResult)
      → RCAResult
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.domain.models import (
    AnalysisRequest,
    MethodologyNotSupportedError,
    MethodologyType,
    RCAResult,
)
from src.domain.methodologies.base import MethodologyRunner
from src.domain.methodologies.five_why import FiveWhyRunner
from src.integrations.llm.openrouter import OpenRouterClient
from src.services.prompt_renderer import PromptRenderer

logger = logging.getLogger(__name__)

# Реестр методик: MethodologyType → runner
_RUNNERS: dict[MethodologyType, MethodologyRunner] = {
    MethodologyType.FIVE_WHY: FiveWhyRunner(),
    # MethodologyType.ISHIKAWA: IshikawaRunner(),  # добавить по мере реализации
    # MethodologyType.RCA_SYSTEMIC: RCASystemicRunner(),
}


class AnalysisService:
    """
    Сервис анализа инцидентов.

    Использование:
        service = AnalysisService()
        result = await service.analyze(request)
    """

    def __init__(
        self,
        llm_client:      OpenRouterClient | None = None,
        prompt_renderer: PromptRenderer | None   = None,
    ) -> None:
        self._llm    = llm_client      or OpenRouterClient()
        self._prompts = prompt_renderer or PromptRenderer()

    async def analyze(self, request: AnalysisRequest) -> RCAResult:
        """
        Запустить полный цикл анализа.

        Args:
            request: валидный AnalysisRequest (contracts.md раздел 2).

        Returns:
            RCAResult (contracts.md раздел 3).

        Raises:
            MethodologyNotSupportedError: если методика ещё не реализована.
            LLMResponseValidationError: если LLM вернул невалидный ответ.
        """
        runner = self._get_runner(request.methodology)

        system_prompt, user_prompt = self._prompts.render(
            template_name=runner.get_prompt_template_name(),
            request=request,
        )

        logger.info(
            "[AnalysisService] Старт | methodology=%s severity=%s",
            request.methodology,
            request.incident.severity,
        )

        async with self._llm as client:
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

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

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
        """Список реализованных методик."""
        return list(_RUNNERS.keys())
