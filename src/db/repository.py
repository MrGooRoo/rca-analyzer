"""
RCA Repository — единственная точка доступа к БД.

Правило: роутеры и сервисы НЕ импортируют sqlalchemy напрямую,
всё проходит через этот модуль.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.orm_models import (
    CausalNodeORM,
    IncidentORM,
    RCAResultORM,
    RecommendationORM,
)
from src.domain.models import CauseNode, RCAResult, Recommendation


class RCARepository:
    """CRUD-операции над результатами RCA."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Запись
    # ------------------------------------------------------------------

    async def save_result(self, result: RCAResult) -> None:
        """
        Сохранить полный результат анализа.
        Если инцидент с таким ID уже существует — не дублировать.
        """
        # 1. Инцидент (upsert-like: проверяем существование)
        existing_incident = await self._session.get(IncidentORM, result.incident_id)
        if existing_incident is None:
            incident_orm = IncidentORM(
                id=result.incident_id,
                title="—",            # реальные поля заполняются из AnalysisRequest
                description="—",
                incident_date=result.created_at,
                location="—",
                incident_type="unknown",
                severity="unknown",
            )
            self._session.add(incident_orm)

        # 2. Результат
        rca_orm = RCAResultORM(
            result_id=result.result_id,
            incident_id=result.incident_id,
            methodology=result.methodology.value,
            summary=result.summary,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
            confidence_avg=result.confidence_avg,
            created_at=result.created_at,
        )
        self._session.add(rca_orm)

        # 3. Узлы причин
        def _nodes(nodes: list[CauseNode], role: str) -> list[CausalNodeORM]:
            return [
                CausalNodeORM(
                    id=str(uuid.uuid4()),
                    result_id=result.result_id,
                    node_id=node.id,
                    node_role=role,
                    text=node.text,
                    category=node.category,
                    level=node.level,
                    parent_id=node.parent_id,
                    confidence=node.confidence,
                )
                for node in nodes
            ]

        self._session.add_all(_nodes(result.immediate_causes, "immediate"))
        self._session.add_all(_nodes(result.contributing_causes, "contributing"))
        self._session.add_all(_nodes(result.root_causes, "root"))

        # 4. Рекомендации
        for rec in result.recommendations:
            self._session.add(
                RecommendationORM(
                    id=str(uuid.uuid4()),
                    result_id=result.result_id,
                    rec_id=rec.id,
                    text=rec.text,
                    priority=rec.priority,
                    category=rec.category,
                    cause_id=rec.cause_id,
                    responsible=rec.responsible,
                    status="open",
                )
            )

        await self._session.commit()

    # ------------------------------------------------------------------
    # Чтение
    # ------------------------------------------------------------------

    async def get_result(self, result_id: str) -> Optional[RCAResult]:
        """Загрузить RCAResult из БД по ID."""
        stmt = (
            select(RCAResultORM)
            .where(RCAResultORM.result_id == result_id)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _orm_to_domain(row)

    async def list_results(
        self,
        incident_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RCAResult]:
        """Список результатов с пагинацией."""
        stmt = (
            select(RCAResultORM)
            .options(
                selectinload(RCAResultORM.causal_nodes),
                selectinload(RCAResultORM.recommendations),
            )
            .order_by(RCAResultORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if incident_id:
            stmt = stmt.where(RCAResultORM.incident_id == incident_id)

        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_domain(r) for r in rows]

    # ------------------------------------------------------------------
    # Обновление статуса рекомендации
    # ------------------------------------------------------------------

    async def update_recommendation_status(
        self, result_id: str, rec_id: str, status: str
    ) -> bool:
        """Обновить статус рекомендации (open/in_progress/closed)."""
        stmt = select(RecommendationORM).where(
            RecommendationORM.result_id == result_id,
            RecommendationORM.rec_id == rec_id,
        )
        rec = (await self._session.execute(stmt)).scalar_one_or_none()
        if rec is None:
            return False
        rec.status = status
        await self._session.commit()
        return True


# ---------------------------------------------------------------------------
# Вспомогательная функция конвертации ORM → Pydantic
# ---------------------------------------------------------------------------

from src.domain.models import MethodologyType  # noqa: E402 (после определений)


def _orm_to_domain(row: RCAResultORM) -> RCAResult:
    def _to_cause(n: CausalNodeORM) -> CauseNode:
        return CauseNode(
            id=n.node_id,
            text=n.text,
            category=n.category,
            level=n.level,
            parent_id=n.parent_id,
            confidence=n.confidence,
        )

    def _to_rec(r: RecommendationORM) -> Recommendation:
        return Recommendation(
            id=r.rec_id,
            text=r.text,
            priority=r.priority,
            category=r.category,
            cause_id=r.cause_id,
            responsible=r.responsible,
        )

    nodes = row.causal_nodes
    return RCAResult(
        result_id=row.result_id,
        incident_id=row.incident_id,
        methodology=MethodologyType(row.methodology),
        created_at=row.created_at,
        immediate_causes=[_to_cause(n) for n in nodes if n.node_role == "immediate"],
        contributing_causes=[_to_cause(n) for n in nodes if n.node_role == "contributing"],
        root_causes=[_to_cause(n) for n in nodes if n.node_role == "root"],
        causal_tree=[_to_cause(n) for n in nodes],
        summary=row.summary,
        recommendations=[_to_rec(r) for r in row.recommendations],
        model_used=row.model_used,
        tokens_used=row.tokens_used,
        confidence_avg=row.confidence_avg,
    )
