"""
Методика «5 Почему» (Five Why).

Algorithm:
1. Получить сформированный ответ LLM (dict из contracts.md раздел 6)
2. Построить линейную цепочку причин (каждый узел ссылается на предыдущий)
3. Последний узел цепочки — корневая причина
4. Вернуть RCAResult
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.domain.methodologies.base import MethodologyRunner
from src.domain.models import (
    AnalysisRequest,
    CauseNode,
    LLMResponseValidationError,
    MethodologyType,
    RCAResult,
    Recommendation,
)


class FiveWhyRunner(MethodologyRunner):
    """
    Реализация методики «5 Почему».

    Особенность: причины выстраиваются в линейную цепочку.
    Непосредственная причина (level=0) → промежуточные (level=1..N-1)
    → корневая причина (последний элемент, level=N).
    """

    @property
    def methodology_type(self) -> str:
        # Возвращаем значение enum (строку), а не сам объект
        # Чтобы get_prompt_template_name() давал «five_why.j2», а не «MethodologyType.FIVE_WHY.j2»
        return MethodologyType.FIVE_WHY.value

    async def run(
        self,
        request: AnalysisRequest,
        raw_llm_response: dict,
    ) -> RCAResult:
        """
        Разобрать ответ LLM и сформировать RCAResult для методики 5 Почему.

        Ожидаемые ключи в raw_llm_response (contracts.md раздел 6):
            - immediate_causes: list[dict]   — обычно 1 элемент
            - contributing_causes: list[dict] — цепочка «pochemu»
            - root_causes: list[dict]         — последнее «pochemu» (1 элемент)
            - summary: str
            - recommendations: list[dict]
        """
        self._validate_response(raw_llm_response)

        immediate    = self._parse_nodes(raw_llm_response.get("immediate_causes", []), level_offset=0)
        contributing = self._parse_nodes(raw_llm_response.get("contributing_causes", []), level_offset=1)
        root         = self._parse_nodes(raw_llm_response.get("root_causes", []), level_offset=len(contributing) + 1)

        all_chain = immediate + contributing + root
        all_chain = self._link_chain(all_chain)

        recommendations = self._parse_recommendations(raw_llm_response.get("recommendations", []))

        confidence_avg = (
            sum(n.confidence for n in all_chain) / len(all_chain)
            if all_chain else 0.0
        )

        return RCAResult(
            result_id=str(uuid.uuid4()),
            incident_id=str(request.incident.incident_date),
            methodology=MethodologyType.FIVE_WHY,
            created_at=datetime.now(UTC),
            immediate_causes=immediate,
            contributing_causes=contributing,
            root_causes=root,
            causal_tree=all_chain,
            summary=raw_llm_response.get("summary", ""),
            recommendations=recommendations,
            model_used=raw_llm_response.get("_meta", {}).get("model", "unknown"),
            tokens_used=raw_llm_response.get("_meta", {}).get("tokens", 0),
            confidence_avg=round(confidence_avg, 3),
        )

    # ---------------------------------------------------------------------------

    def _validate_response(self, response: dict) -> None:
        required = {"immediate_causes", "root_causes", "summary", "recommendations"}
        missing = required - set(response.keys())
        if missing:
            raise LLMResponseValidationError(
                f"[FiveWhy] Отсутствуют обязательные ключи в ответе LLM: {missing}"
            )

    def _parse_nodes(self, raw_nodes: list[dict], level_offset: int) -> list[CauseNode]:
        nodes = []
        for i, raw in enumerate(raw_nodes):
            try:
                node = CauseNode(
                    id=raw.get("id") or str(uuid.uuid4()),
                    text=raw["text"],
                    category=raw.get("category", "не определено"),
                    level=level_offset + i,
                    parent_id=raw.get("parent_id"),
                    confidence=float(raw.get("confidence", 0.5)),
                )
            except (KeyError, ValueError) as exc:
                raise LLMResponseValidationError(
                    f"[FiveWhy] Ошибка парсинга узла {raw}: {exc}"
                ) from exc
            nodes.append(node)
        return nodes

    def _link_chain(self, nodes: list[CauseNode]) -> list[CauseNode]:
        linked = []
        for i, node in enumerate(nodes):
            parent_id = nodes[i - 1].id if i > 0 else None
            linked.append(node.model_copy(update={"parent_id": parent_id, "level": i}))
        return linked

    def _parse_recommendations(self, raw_recs: list[dict]) -> list[Recommendation]:
        result = []
        for raw in raw_recs:
            try:
                rec = Recommendation(
                    id=raw.get("id") or str(uuid.uuid4()),
                    text=raw["text"],
                    priority=raw.get("priority", "medium"),
                    category=raw.get("category", "short_term"),
                    cause_id=raw["cause_id"],
                    responsible=raw.get("responsible"),
                )
            except (KeyError, ValueError) as exc:
                raise LLMResponseValidationError(
                    f"[FiveWhy] Ошибка парсинга рекомендации {raw}: {exc}"
                ) from exc
            result.append(rec)
        return result
