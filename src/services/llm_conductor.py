"""P17 LLM Conductor: draft model + threshold-gated verifier model."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from src.domain.methodologies import METHODOLOGY_NAMES_RU
from src.domain.methodologies.base import MethodologyRunner
from src.domain.models import AnalysisRequest, CauseNode, LLMSettings, RCAResult
from src.integrations.llm.openrouter import OpenRouterClient
from src.services.prompt_renderer import PromptRenderer

logger = logging.getLogger(__name__)

_VERIFIER_TEMPLATE = "verifier.j2"
_LOW_CONFIDENCE_FALLBACK_THRESHOLD = 0.7

_OUTPUT_SCHEMA_HINT = """
Верни JSON, совместимый с исходной методологией и существующим parser/runner.

Минимальный общий контракт:
{
  "immediate_causes": [
    {"id": "string", "text": "string", "category": "string", "level": 0,
     "parent_id": null, "confidence": 0.0}
  ],
  "contributing_causes": [
    {"id": "string", "text": "string", "category": "string", "level": 1,
     "parent_id": "string", "confidence": 0.0}
  ],
  "root_causes": [
    {"id": "string", "text": "string", "category": "string", "level": 2,
     "parent_id": "string", "confidence": 0.0}
  ],
  "summary": "string",
  "recommendations": [
    {"id": "string", "text": "string", "priority": "high|medium|low",
     "category": "immediate|short_term|systemic", "cause_id": "string",
     "responsible": "string|null"}
  ]
}

Если в черновике есть дополнительные обязательные ключи конкретной методологии
(например top_event/hazard/threats/consequences для BowTie или top_event для FTA),
сохрани и улучшай их тоже: итоговый JSON должен разбираться тем же runner'ом.
""".strip()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


class LLMConductor:
    """
    Orchestrates P17 two-step analysis.

    Flow:
      1. draft_model renders methodology prompt and produces raw methodology JSON;
      2. runner parses draft JSON into RCAResult and exposes confidence_avg;
      3. verification gate decides whether verifier_model is needed;
      4. verifier_model receives incident + draft JSON + low-confidence nodes;
      5. runner parses verified JSON into final RCAResult.
    """

    def __init__(
        self,
        settings: LLMSettings,
        *,
        llm_factory: Callable[..., Any] = OpenRouterClient,
        prompt_renderer: PromptRenderer | None = None,
    ) -> None:
        self._settings = settings
        self._llm_factory = llm_factory
        self._prompts = prompt_renderer or PromptRenderer()

    async def analyze(self, request: AnalysisRequest, runner: MethodologyRunner) -> RCAResult:
        """Run draft analysis and optionally verifier pass according to settings."""
        system_prompt, user_prompt = self._prompts.render(
            template_name=runner.get_prompt_template_name(),
            request=request,
        )

        draft_raw = await self._complete_with_model(
            model=self._settings.draft_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        draft_result = await runner.run(request, draft_raw)

        if not self._should_verify(draft_result):
            logger.info(
                "[LLMConductor] verifier skipped | scheme=%s confidence=%.3f threshold=%.3f",
                self._settings.verification_scheme,
                draft_result.confidence_avg,
                self._settings.quality_threshold,
            )
            return draft_result

        verifier_model = self._settings.verifier_model
        if not verifier_model:
            logger.warning("[LLMConductor] verifier requested but verifier_model is empty")
            return draft_result

        verifier_system, verifier_user = self._prompts.render(
            template_name=_VERIFIER_TEMPLATE,
            request=request,
            extra_context={
                "methodology": self._methodology_name(request),
                "draft_result_json": _json_dumps(draft_raw),
                "low_confidence_nodes": self._low_confidence_nodes(draft_result),
                "output_schema_hint": _OUTPUT_SCHEMA_HINT,
            },
        )
        verifier_raw = await self._complete_with_model(
            model=verifier_model,
            system_prompt=verifier_system,
            user_prompt=verifier_user,
        )
        final_result = await runner.run(request, verifier_raw)
        return self._merge_model_metadata(final_result, draft_raw, verifier_raw)

    async def _complete_with_model(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        """Call a specific OpenRouter model without hidden fallback-model substitution."""
        async with self._llm_factory(model=model, fallback_models=[]) as client:
            return await client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

    def _should_verify(self, draft_result: RCAResult) -> bool:
        scheme = self._settings.verification_scheme
        if scheme == "disabled":
            return False
        if scheme == "always":
            return True
        if scheme == "threshold":
            return draft_result.confidence_avg < self._settings.quality_threshold
        return False

    def _low_confidence_nodes(self, result: RCAResult) -> list[dict[str, Any]]:
        """Return unique low-confidence nodes for verifier prompt."""
        threshold = self._settings.quality_threshold or _LOW_CONFIDENCE_FALLBACK_THRESHOLD
        seen: set[str] = set()
        low_nodes: list[dict[str, Any]] = []
        nodes = result.causal_tree or (
            result.immediate_causes + result.contributing_causes + result.root_causes
        )
        for node in nodes:
            if node.id in seen or node.confidence >= threshold:
                continue
            seen.add(node.id)
            low_nodes.append(_node_to_prompt_dict(node))
        return low_nodes

    def _merge_model_metadata(
        self,
        final_result: RCAResult,
        draft_raw: dict,
        verifier_raw: dict,
    ) -> RCAResult:
        draft_meta = draft_raw.get("_meta", {}) if isinstance(draft_raw, dict) else {}
        verifier_meta = verifier_raw.get("_meta", {}) if isinstance(verifier_raw, dict) else {}
        draft_model = draft_meta.get("model") or self._settings.draft_model
        verifier_model = verifier_meta.get("model") or self._settings.verifier_model or "unknown"
        draft_tokens = int(draft_meta.get("tokens") or 0)
        verifier_tokens = int(verifier_meta.get("tokens") or 0)

        return final_result.model_copy(
            update={
                "model_used": f"{draft_model} -> {verifier_model}",
                "tokens_used": draft_tokens + verifier_tokens,
            }
        )

    @staticmethod
    def _methodology_name(request: AnalysisRequest) -> str:
        value = getattr(request.methodology, "value", str(request.methodology))
        return METHODOLOGY_NAMES_RU.get(value, value)


def _node_to_prompt_dict(node: CauseNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "text": node.text,
        "category": node.category,
        "level": node.level,
        "parent_id": node.parent_id,
        "confidence": node.confidence,
    }
