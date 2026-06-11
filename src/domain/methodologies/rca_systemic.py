"""
Методика «Системный RCA» (основная методика проекта).

Algorithm:
1. LLM анализирует инцидент на всех системных уровнях:
   - непосредственные / человеческие ошибки
   - условия / предшествующие факторы
   - ототсутствие/неисправность защитных барьеров (barriers)
2. Каждая группа причин помечается системным уровнем (SystemLevel)
3. barriers = список защитных барьеров из LLM (провалились / отсутствовали / были обхождены)
4. causal_tree        = все узлы, упорядоченные по системным уровням
Отличается от FTA/Исикавы: фокус на системных дисфункциях и проваленных барьерах.
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

# Системные уровни анализа (HFACS-подобная классификация)
SYSTEM_LEVELS = {
    "небезопасные действия",     # Unsafe Acts
    "предшествующие условия",  # Preconditions
    "надзор и управление",        # Supervision
    "организационные влияния",   # Organisational Influences
    "барьеры",                       # Barriers / Safeguards
}


class RcaSystemicRunner(MethodologyRunner):
    """
    Реализация методики «Системный RCA».

    Особенность: причины классифицируются по системным уровням,
    а барьеры защиты хранятся в CauseNode.category = "barrier".
    immediate_causes  → небезопасные действия
    contributing_causes → предшествующие условия + надзор
    root_causes        → организационные причины + провалившиеся барьеры
    """

    @property
    def methodology_type(self) -> str:
        return MethodologyType.RCA_SYSTEMIC.value

    async def run(
        self,
        request: AnalysisRequest,
        raw_llm_response: dict,
    ) -> RCAResult:
        """
        Ожидаемые ключи (contracts.md раздел 6 + barrier):
            - immediate_causes: list[dict]     — небезопасные действия
            - contributing_causes: list[dict]  — условия, надзор
            - root_causes: list[dict]          — организационные / барьеры
            - barriers: list[dict]             — защитные барьеры (breach/absent)
            - summary: str
            - recommendations: list[dict]
        """
        self._validate_response(raw_llm_response)

        immediate    = self._parse_nodes(raw_llm_response.get("immediate_causes", []))
        contributing = self._parse_nodes(raw_llm_response.get("contributing_causes", []))
        root         = self._parse_nodes(raw_llm_response.get("root_causes", []))
        barriers     = self._parse_barrier_nodes(raw_llm_response.get("barriers", []))

        # Барьеры добавляем в root_causes: проваленные защиты — корневые проблемы
        effective_root = root + barriers

        causal_tree = immediate + contributing + effective_root

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
            methodology=MethodologyType.RCA_SYSTEMIC,
            created_at=datetime.now(UTC),
            immediate_causes=immediate,
            contributing_causes=contributing,
            root_causes=effective_root,
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
        required = {"immediate_causes", "contributing_causes", "root_causes",
                    "summary", "recommendations"}
        missing = required - set(response.keys())
        if missing:
            raise LLMResponseValidationError(
                f"[RcaSystemic] Отсутствуют обязательные ключи: {missing}"
            )

    # Публичный алиас для обратной совместимости с тестами
    validate_response = _validate_response

    def _parse_nodes(self, raw_nodes: list[dict]) -> list[CauseNode]:
        nodes = []
        for raw in raw_nodes:
            try:
                node = CauseNode(
                    id=raw.get("id") or str(uuid.uuid4()),
                    text=raw["text"],
                    category=raw.get("category", "не определено"),
                    level=int(raw.get("level", 1)),
                    parent_id=raw.get("parent_id"),
                    confidence=float(raw.get("confidence", 0.5)),
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise LLMResponseValidationError(
                    f"[RcaSystemic] Ошибка парсинга узла {raw}: {exc}"
                ) from exc
            nodes.append(node)
        return nodes

    def _parse_barrier_nodes(self, raw_barriers: list[dict]) -> list[CauseNode]:
        """
        Барьеры парсим как CauseNode с category="barrier".
        Дополнительный ключ status: absent | breached | failed — пишем в text.
        """
        nodes = []
        for raw in raw_barriers:
            try:
                status = raw.get("status", "failed")
                text = raw["text"]
                full_text = f"[{status.upper()}] {text}"
                node = CauseNode(
                    id=raw.get("id") or str(uuid.uuid4()),
                    text=full_text,
                    category="barrier",
                    level=int(raw.get("level", 2)),
                    parent_id=raw.get("parent_id"),
                    confidence=float(raw.get("confidence", 0.5)),
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise LLMResponseValidationError(
                    f"[RcaSystemic] Ошибка парсинга барьеры {raw}: {exc}"
                ) from exc
            nodes.append(node)
        return nodes

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
                    f"[RcaSystemic] Ошибка парсинга рекомендации {raw}: {exc}"
                ) from exc
            result.append(rec)
        return result
