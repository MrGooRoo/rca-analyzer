"""
Методика «Fault Tree Analysis» (Дерево отказов).

Algorithm:
1. LLM строит дерево отказов топ-даун (верхнее событие → промежуточные события → базовые события)
2. Каждый узел помечен логическим затвором: AND (все дочерние нужны) | OR (достаточно одного) | BASIC (листовой узел)
3. immediate_causes  = топ-узел (нежелательное событие, level=0)
4. contributing_causes = промежуточные / подчинённые события (level>=1)
5. root_causes        = базовые события (листья дерева, BASIC, без дочерних)
6. causal_tree        = все узлы с корректными parent_id и gate
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
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

# Допустимые затворы FTA
FTA_GATES = {"AND", "OR", "BASIC", "INHIBIT", "NOT", "XOR"}


@dataclass
class FtaNode(CauseNode):
    """Расширенный CauseNode с затвором FTA."""
    gate: str = "OR"  # AND | OR | BASIC | INHIBIT | NOT | XOR


class FaultTreeRunner(MethodologyRunner):
    """
    Реализация Fault Tree Analysis.

    Особенность: дерево отказов развивается сверху вниз (top-down).
    Каждый узел содержит gate-атрибут, хранящийся в CauseNode.category.
    Базовые события (BASIC gate) не имеют дочерних — это root_causes.
    """

    @property
    def methodology_type(self) -> str:
        return MethodologyType.FTA.value

    async def run(
        self,
        request: AnalysisRequest,
        raw_llm_response: dict,
    ) -> RCAResult:
        """
        Ожидаемые ключи (contracts.md раздел 6, расширенный для FTA):
            - top_event: dict           — верхнее нежелательное событие
            - immediate_causes: list    — первый уровень под top_event
            - contributing_causes: list — промежуточные узлы
            - root_causes: list         — базовые события (BASIC gate)
            - summary: str
            - recommendations: list
        """
        self._validate_response(raw_llm_response)

        # top_event — голова дерева, помещаем в immediate_causes (level=0)
        top_raw = raw_llm_response["top_event"]
        top_node = self._parse_single_node(top_raw, default_level=0)

        immediate    = self._parse_nodes(raw_llm_response.get("immediate_causes", []))
        contributing = self._parse_nodes(raw_llm_response.get("contributing_causes", []))
        root         = self._parse_nodes(raw_llm_response.get("root_causes", []))

        # Если immediate-узлы без parent_id — привязываем к top_node
        immediate = self._link_to_parent(immediate, top_node.id)

        causal_tree = [top_node] + immediate + contributing + root

        recommendations = self._parse_recommendations(
            raw_llm_response.get("recommendations", [])
        )

        all_nodes = causal_tree
        confidence_avg = (
            round(sum(n.confidence for n in all_nodes) / len(all_nodes), 3)
            if all_nodes else 0.0
        )

        return RCAResult(
            result_id=str(uuid.uuid4()),
            incident_id=str(request.incident.incident_date),
            methodology=MethodologyType.FTA,
            created_at=datetime.now(UTC),
            immediate_causes=[top_node] + immediate,
            contributing_causes=contributing,
            root_causes=root,
            causal_tree=causal_tree,
            summary=raw_llm_response.get("summary", ""),
            recommendations=recommendations,
            model_used=raw_llm_response.get("_meta", {}).get("model", "unknown"),
            tokens_used=raw_llm_response.get("_meta", {}).get("tokens", 0),
            confidence_avg=confidence_avg,
        )

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _validate_response(self, response: dict) -> None:
        required = {"top_event", "immediate_causes", "root_causes",
                    "summary", "recommendations"}
        missing = required - set(response.keys())
        if missing:
            raise LLMResponseValidationError(
                f"[FTA] Отсутствуют обязательные ключи в ответе LLM: {missing}"
            )
        if not isinstance(response["top_event"], dict):
            raise LLMResponseValidationError("[FTA] top_event должен быть объектом")

    def _parse_single_node(self, raw: dict, default_level: int = 0) -> CauseNode:
        try:
            gate = raw.get("gate", "OR").upper()
            return CauseNode(
                id=raw.get("id") or str(uuid.uuid4()),
                text=raw["text"],
                # gate храним в category: "FTA:OR", "FTA:AND", "FTA:BASIC"
                category=f"FTA:{gate}",
                level=int(raw.get("level", default_level)),
                parent_id=raw.get("parent_id"),
                confidence=float(raw.get("confidence", 0.5)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise LLMResponseValidationError(
                f"[FTA] Ошибка парсинга узла {raw}: {exc}"
            ) from exc

    def _parse_nodes(self, raw_nodes: list[dict]) -> list[CauseNode]:
        return [self._parse_single_node(raw) for raw in raw_nodes]

    def _link_to_parent(
        self, nodes: list[CauseNode], parent_id: str
    ) -> list[CauseNode]:
        """immediate-узлы без parent_id привязываем к top_node."""
        result = []
        for node in nodes:
            if node.parent_id is None:
                node = node.model_copy(update={"parent_id": parent_id})
            result.append(node)
        return result

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
                    f"[FTA] Ошибка парсинга рекомендации {raw}: {exc}"
                ) from exc
            result.append(rec)
        return result
