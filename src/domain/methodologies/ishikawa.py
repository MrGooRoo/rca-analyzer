"""
Методика «Диаграмма Исикавы» (Fishbone / Причинно-следственная диаграмма).

Algorithm:
1. LLM возвращает причины, сгруппированные по 6 категориям «6M»:
   человек (Man), метод (Method), машина (Machine),
   материал (Material), среда (Environment), измерение (Measurement)
2. Каждая категория может содержать несколько ветвей причин
3. contributing_causes = все причины из всех ветвей (уровень 1)
4. root_causes        = самые глубокие причины каждой ветви (level >= 2)
5. causal_tree        = все узлы с корректными parent_id (дерево, не цепочка)
"""

from __future__ import annotations

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

# Признанные категории Исикавы (6M + управление из contracts.md)
ISHIKAWA_CATEGORIES = {
    "человек", "man", "people",
    "метод", "method", "process",
    "машина", "machine", "equipment",
    "материал", "material",
    "среда", "environment",
    "измерение", "measurement",
    "управление", "management",
}


class IshikawaRunner(MethodologyRunner):
    """
    Реализация методики «Диаграмма Исикавы».

    Особенность: причины группируются по категориям (ветви рыбьей кости).
    Каждая ветвь — независимое поддерево, а не линейная цепочка.
    immediate_causes  → «голова рыбы» (сам инцидент/эффект)
    contributing_causes → причины первого уровня по каждой ветви
    root_causes        → глубинные причины (самые дальние от головы)
    """

    @property
    def methodology_type(self) -> str:
        return MethodologyType.ISHIKAWA.value

    async def run(
        self,
        request: AnalysisRequest,
        raw_llm_response: dict,
    ) -> RCAResult:
        """
        Разобрать ответ LLM и сформировать RCAResult для Исикавы.

        Ожидаемые ключи (contracts.md раздел 6):
            - immediate_causes: list[dict]    — «голова» (эффект/симптом)
            - contributing_causes: list[dict] — ветви по категориям
            - root_causes: list[dict]         — глубинные причины
            - summary: str
            - recommendations: list[dict]
        """
        self._validate_response(raw_llm_response)

        immediate    = self._parse_nodes(raw_llm_response.get("immediate_causes", []))
        contributing = self._parse_nodes(raw_llm_response.get("contributing_causes", []))
        root         = self._parse_nodes(raw_llm_response.get("root_causes", []))

        # Дерево: все узлы объединяем, связи уже заданы через parent_id от LLM
        causal_tree = self._build_tree(immediate, contributing, root)

        # Берём contributing_causes из патченного causal_tree, чтобы parent_id был актуальным
        tree_node_map = {n.id: n for n in causal_tree}
        contributing = [tree_node_map.get(c.id, c) for c in contributing]

        recommendations = self._parse_recommendations(
            raw_llm_response.get("recommendations", [])
        )

        all_nodes = immediate + contributing + root
        confidence_avg = (
            round(sum(n.confidence for n in all_nodes) / len(all_nodes), 3)
            if all_nodes else 0.0
        )

        return RCAResult(
            result_id=str(uuid.uuid4()),
            incident_id=str(request.incident.incident_date),
            methodology=MethodologyType.ISHIKAWA,
            created_at=datetime.now(timezone.utc),
            immediate_causes=immediate,
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
        required = {"immediate_causes", "contributing_causes", "root_causes",
                    "summary", "recommendations"}
        missing = required - set(response.keys())
        if missing:
            raise LLMResponseValidationError(
                f"[Ishikawa] Отсутствуют обязательные ключи в ответе LLM: {missing}"
            )

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
                    f"[Ishikawa] Ошибка парсинга узла {raw}: {exc}"
                ) from exc
            nodes.append(node)
        return nodes

    def _build_tree(
        self,
        immediate: list[CauseNode],
        contributing: list[CauseNode],
        root: list[CauseNode],
    ) -> list[CauseNode]:
        """
        Собрать causal_tree из всех узлов.

        Если у contributing-узла нет parent_id — привязываем к первому
        immediate-узлу (голове рыбы), имитируя структуру диаграммы.
        """
        head_id = immediate[0].id if immediate else None
        fixed: list[CauseNode] = list(immediate)

        for node in contributing:
            if node.parent_id is None and head_id:
                node = node.model_copy(update={"parent_id": head_id})
            fixed.append(node)

        # Для root_causes: если нет parent_id — не меняем (LLM должна указать)
        fixed.extend(root)
        return fixed

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
                    f"[Ishikawa] Ошибка парсинга рекомендации {raw}: {exc}"
                ) from exc
            result.append(rec)
        return result
