"""
Юнит-тесты для сущности «исследование» (analysis_session).
"""

from __future__ import annotations

from datetime import datetime

from src.domain.models import (
    AnalysisSession,
    CauseNode,
    MethodologyType,
    RCAResult,
    Recommendation,
)

# -----------------------------------------------------------------------
# Фабрики
# -----------------------------------------------------------------------

def _make_result(
    result_id: str = "r-001",
    incident_id: str = "inc-001",
    session_id: str | None = None,
    methodology: MethodologyType = MethodologyType.FIVE_WHY,
) -> RCAResult:
    node = CauseNode(id="n1", text="Причина", category="среда", level=0, confidence=0.8)
    return RCAResult(
        result_id=result_id,
        incident_id=incident_id,
        session_id=session_id,
        methodology=methodology,
        created_at=datetime(2026, 6, 13, 12, 0),
        immediate_causes=[node],
        contributing_causes=[],
        root_causes=[node],
        causal_tree=[node],
        summary="Тестовый анализ",
        recommendations=[
            Recommendation(id="rec1", text="Рекомендация", priority="high",
                           category="immediate", cause_id="n1")
        ],
        model_used="test-model",
        tokens_used=100,
        confidence_avg=0.8,
    )


def _make_session(
    session_id: str = "sess-001",
    results: list[RCAResult] | None = None,
) -> AnalysisSession:
    if results is not None:
        for r in results:
            r.session_id = session_id
    return AnalysisSession(
        id=session_id,
        created_at=datetime(2026, 6, 13, 12, 0),
        user_id="user-001",
        incident_title="Падение с лестницы",
        incident_description="Работник упал",
        incident_date=datetime(2026, 6, 13, 9, 0),
        incident_location="Цех №1",
        incident_type="injury",
        incident_severity="moderate",
        results=results or [],
    )


# -----------------------------------------------------------------------
# Тесты AnalysisSession-модели
# -----------------------------------------------------------------------

class TestAnalysisSessionModel:

    def test_create_empty_session(self):
        session = _make_session()
        assert session.id == "sess-001"
        assert session.incident_title == "Падение с лестницы"
        assert session.incident_severity == "moderate"
        assert session.results == []

    def test_session_with_results(self):
        r1 = _make_result(result_id="r-001", methodology=MethodologyType.FIVE_WHY)
        r2 = _make_result(result_id="r-002", methodology=MethodologyType.ISHIKAWA)
        session = _make_session(results=[r1, r2])
        assert len(session.results) == 2
        assert session.results[0].session_id == "sess-001"
        assert session.results[1].session_id == "sess-001"

    def test_session_serialization(self):
        session = _make_session()
        data = session.model_dump(mode="json")
        assert data["id"] == "sess-001"
        assert data["incident_title"] == "Падение с лестницы"
        assert data["incident_severity"] == "moderate"

    def test_session_with_incident_data_json(self):
        import json
        incident_data = {"title": "Test", "description": "Desc", "victims": 2}
        session = _make_session()
        session.incident_data_json = json.dumps(incident_data, ensure_ascii=False)
        data = session.model_dump(mode="json")
        parsed = json.loads(data["incident_data_json"])
        assert parsed["victims"] == 2


# -----------------------------------------------------------------------
# Тесты RCAResult с session_id
# -----------------------------------------------------------------------

class TestRCAResultSessionId:

    def test_result_without_session_id(self):
        result = _make_result()
        assert result.session_id is None

    def test_result_with_session_id(self):
        result = _make_result(session_id="sess-001")
        assert result.session_id == "sess-001"

    def test_result_session_id_serialized(self):
        result = _make_result(session_id="sess-001")
        data = result.model_dump(mode="json")
        assert data["session_id"] == "sess-001"

    def test_result_session_id_none_serialized(self):
        result = _make_result()
        data = result.model_dump(mode="json")
        assert data["session_id"] is None

    def test_multi_results_share_session_id(self):
        """Результаты multi-анализа имеют общий session_id."""
        session_id = "sess-multi-001"
        r1 = _make_result(result_id="r-001", session_id=session_id,
                           methodology=MethodologyType.FIVE_WHY)
        r2 = _make_result(result_id="r-002", session_id=session_id,
                           methodology=MethodologyType.ISHIKAWA)
        assert r1.session_id == r2.session_id == session_id


# -----------------------------------------------------------------------
# Тесты compute_incident_hash
# -----------------------------------------------------------------------

class TestComputeIncidentHash:

    def test_same_input_same_hash(self):
        from src.db.repository import compute_incident_hash
        h1 = compute_incident_hash("Падение с лестницы", "Работник упал")
        h2 = compute_incident_hash("Падение с лестницы", "Работник упал")
        assert h1 == h2

    def test_different_input_different_hash(self):
        from src.db.repository import compute_incident_hash
        h1 = compute_incident_hash("Падение с лестницы", "Работник упал")
        h2 = compute_incident_hash("Удар током", "Поражение электротоком")
        assert h1 != h2

    def test_case_insensitive(self):
        from src.db.repository import compute_incident_hash
        h1 = compute_incident_hash("Падение с лестницы", "Работник упал")
        h2 = compute_incident_hash("падение с лестницы", "работник упал")
        assert h1 == h2

    def test_whitespace_normalized(self):
        from src.db.repository import compute_incident_hash
        h1 = compute_incident_hash("Падение", "Работник упал")
        h2 = compute_incident_hash("  Падение  ", "  Работник упал  ")
        assert h1 == h2

    def test_hash_length(self):
        from src.db.repository import compute_incident_hash
        h = compute_incident_hash("Test", "Desc")
        assert len(h) == 64  # SHA-256 hex digest

    def test_same_incident_different_methodology_same_hash(self):
        """Тот же инцидент, проанализированный разными методиками — одинаковый hash."""
        from src.db.repository import compute_incident_hash
        h1 = compute_incident_hash("Падение", "Упал с высоты 2м")
        h2 = compute_incident_hash("Падение", "Упал с высоты 2м")
        # Независимо от того, какой methodology — hash одинаковый
        assert h1 == h2
