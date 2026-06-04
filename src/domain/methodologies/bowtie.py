"""
Методика «Бабочка / Bowtie Analysis».

Algorithm:
1. LLM строит би-направленную диаграмму:
   ЛЕВОЕ крыло: угрозы (threats) + барьеры предотвращения (prevention_barriers)
   ЦЕНТР: опасный фактор (hazard) + верхнее событие (top_event / узел бабочки)
   ПРАВОЕ крыло: последствия (consequences) + барьеры смягчения (mitigation_barriers)
2. Отображение в RCAResult:
   immediate_causes    = top_event + consequences
   contributing_causes = prevention_barriers + mitigation_barriers
   root_causes         = threats
   causal_tree         = все узлы (hazard + top_event + threats + barriers + consequences)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.domain.models import (
    AnalysisRequest,
    CauseNode,
    LLMResponseValidationError,
    MethodologyType,
    RCAResult,
    Recommendation,
)
from src.domain.methodologies.base import MethodologyRunner

logger = logging.getLogger(__name__)


class BowTieRunner(MethodologyRunner):
    """
    Реализация Bowtie Analysis.

    Особенность: би-направленная структура (threats → top_event → consequences).
    Барьеры отображаются через category = "BOWTIE:PREVENTION" / "BOWTIE:MITIGATION".
    Признак degraded=true хранится в CauseNode.confidence (снижено до 0.0–0.3).

    Валидация целостности (warnings, не ошибки):
    - каждый threat должен иметь минимум 1 prevention_barrier
    - каждый consequence должен иметь минимум 1 mitigation_barrier
    """

    @property
    def methodology_type(self) -> str:
        return MethodologyType.BOWTIE.value

    async def run(
        self,
        request: AnalysisRequest,
        raw_llm_response: dict,
    ) -> RCAResult:
        """
        Ожидаемые ключи LLM-ответа:
            - hazard:               dict
            - top_event:            dict
            - threats:              list[dict]
            - prevention_barriers:  list[dict]
            - consequences:         list[dict]
            - mitigation_barriers:  list[dict]
            - summary:              str
            - recommendations:      list[dict]
        """
        self._validate_response(raw_llm_response)
        self._warn_incomplete_barriers(raw_llm_response)

        hazard   = self._parse_node(raw_llm_response["hazard"],   default_level=-1)
        top_node = self._parse_node(raw_llm_response["top_event"], default_level=0)

        threats      = self._parse_nodes(raw_llm_response.get("threats", []))
        prev_bars    = self._parse_nodes(raw_llm_response.get("prevention_barriers", []))
        consequences = self._parse_nodes(raw_llm_response.get("consequences", []))
        miti_bars    = self._parse_nodes(raw_llm_response.get("mitigation_barriers", []))

        # Суммарное отображение в терминах RCAResult
        immediate_causes    = [top_node] + consequences
        contributing_causes = prev_bars + miti_bars
        root_causes         = threats
        causal_tree         = (
            [hazard, top_node]
            + threats
            + prev_bars
            + consequences
            + miti_bars
        )

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
            methodology=MethodologyType.BOWTIE,
            created_at=datetime.now(timezone.utc),
            immediate_causes=immediate_causes,
            contributing_causes=contributing_causes,
            root_causes=root_causes,
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
        """Hard валидация: отсутствующие ключи → LLMResponseValidationError."""
        required = {
            "hazard", "top_event", "threats",
            "consequences", "summary", "recommendations",
        }
        missing = required - set(response.keys())
        if missing:
            raise LLMResponseValidationError(
                f"[BowTie] Отсутствуют обязательные ключи в ответе LLM: {missing}"
            )
        for key in ("hazard", "top_event"):
            if not isinstance(response[key], dict):
                raise LLMResponseValidationError(
                    f"[BowTie] '{key}' должен быть объектом"
                )

    def _warn_incomplete_barriers(self, response: dict) -> None:
        """
        Soft валидация: проверяет целостность Bowtie-диаграммы.
        Нарушения не прерывают обработку (это вина LLM), но фиксируются в логах.
        """
        threat_ids = {t.get("id") for t in response.get("threats", []) if t.get("id")}
        prevented_ids = {
            b.get("parent_id") for b in response.get("prevention_barriers", [])
        }
        unprotected_threats = threat_ids - prevented_ids
        if unprotected_threats:
            logger.warning(
                "[BowTie] Угрозы без prevention_barrier: %s",
                unprotected_threats,
            )

        consequence_ids = {
            c.get("id") for c in response.get("consequences", []) if c.get("id")
        }
        mitigated_ids = {
            b.get("parent_id") for b in response.get("mitigation_barriers", [])
        }
        unmitigated_consequences = consequence_ids - mitigated_ids
        if unmitigated_consequences:
            logger.warning(
                "[BowTie] Последствия без mitigation_barrier: %s",
                unmitigated_consequences,
            )

    def _parse_node(self, raw: dict, default_level: int = 0) -> CauseNode:
        """Парсинг узла Bowtie в CauseNode."""
        try:
            raw_confidence = raw.get("confidence", 0.5)
            # Деградированные барьеры: понижаем confidence до 0.15
            degraded = bool(raw.get("degraded", False))
            if degraded and raw_confidence > 0.3:
                raw_confidence = 0.15

            return CauseNode(
                id=raw.get("id") or str(uuid.uuid4()),
                text=raw["text"],
                category=raw.get("category", "BOWTIE:UNKNOWN"),
                level=int(raw.get("level", default_level)),
                parent_id=raw.get("parent_id"),
                confidence=float(raw_confidence),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise LLMResponseValidationError(
                f"[BowTie] Ошибка парсинга узла {raw}: {exc}"
            ) from exc

    def _parse_nodes(self, raw_nodes: list[dict]) -> list[CauseNode]:
        return [self._parse_node(raw) for raw in raw_nodes]

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
                    f"[BowTie] Ошибка парсинга рекомендации {raw}: {exc}"
                ) from exc
            result.append(rec)
        return result
