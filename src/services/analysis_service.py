"""
Оркестратор анализа корневых причин.

Поток:
  AnalysisRequest
      → PromptRenderer (Jinja2 → system + user prompt)
      → OpenRouterClient (LLM вызов с retry)
      → MethodologyRunner (raw dict → RCAResult)
      → RCAResult
Примечание по жизненному циклу httpx:
    OpenRouterClient создаётся свежим на каждый запрос (через async with),
    чтобы избежать повторного использования закрытого httpx.AsyncClient.
"""

from __future__ import annotations

import logging

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

_RUNNERS: dict[MethodologyType, MethodologyRunner] = {
    MethodologyType.FIVE_WHY: FiveWhyRunner(),
}


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
        # None → создавать новый клиент на каждый запрос
        self._llm_factory = (lambda: llm_client) if llm_client else OpenRouterClient
        self._prompts     = prompt_renderer or PromptRenderer()

    async def analyze(self, request: AnalysisRequest) -> RCAResult:
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

        # Новый httpx-клиент на каждый запрос — безопасно закрывается после
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
