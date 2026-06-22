"""
Тесты для сравнения методик и multi-analyze.
Покрывают: валидацию MultiAnalysisRequest, AnalysisService.compare(),
           роуты /analyze-multi и /results/compare.
Запуск: pytest tests/unit/test_compare.py
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.domain.models import (
    CauseNode,
    IncidentInput,
    MethodologyType,
    MultiAnalysisRequest,
    RCAResult,
    Recommendation,
)
from src.services.analysis_service import AnalysisService, _texts_are_similar

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

def _make_result(
    methodology: MethodologyType,
    root_texts: list[str] | None = None,
    imm_texts: list[str] | None = None,
    contrib_texts: list[str] | None = None,
    rec_texts: list[str] | None = None,
    confidence: float = 0.8,
) -> RCAResult:
    """Быстро собрать RCAResult для тестов сравнения."""
    root = [CauseNode(id=f"r{i}", text=t, category="root", level=2, confidence=0.8)
            for i, t in enumerate(root_texts or [])]
    imm = [CauseNode(id=f"im{i}", text=t, category="immediate", level=0, confidence=0.9)
           for i, t in enumerate(imm_texts or [])]
    contrib = [CauseNode(id=f"c{i}", text=t, category="contributing", level=1, confidence=0.7)
               for i, t in enumerate(contrib_texts or [])]
    recs = [Recommendation(id=f"rec{i}", text=t, priority="high", category="systemic", cause_id=f"r{i}")
            for i, t in enumerate(rec_texts or [])]
    return RCAResult(
        result_id=f"res-{methodology.value}",
        incident_id="inc-test-001",
        methodology=methodology,
        created_at=datetime(2026, 6, 8, 12, 0),
        root_causes=root,
        contributing_causes=contrib,
        immediate_causes=imm,
        causal_tree=root + contrib + imm,
        summary=f"Анализ ({methodology.value})",
        recommendations=recs,
        model_used="test-model",
        tokens_used=100,
        confidence_avg=confidence,
    )


@pytest.fixture
def incident() -> IncidentInput:
    return IncidentInput(
        title="Падение с лестницы",
        description="Работник поскользнулся.",
        incident_type="injury",
        severity="moderate",
    )


# ---------------------------------------------------------------------------
# 1. Валидация MultiAnalysisRequest
# ---------------------------------------------------------------------------

class TestMultiAnalysisRequestValidation:

    def test_min_2_methodologies_required(self, incident):
        """Меньше 2 методик — ошибка валидации."""
        with pytest.raises(ValidationError):
            MultiAnalysisRequest(
                methodologies=[MethodologyType.FIVE_WHY],
                incident=incident,
            )

    def test_max_5_methodologies(self, incident):
        """Больше 5 методик — ошибка валидации."""
        with pytest.raises(ValidationError):
            MultiAnalysisRequest(
                methodologies=[
                    MethodologyType.FIVE_WHY,
                    MethodologyType.ISHIKAWA,
                    MethodologyType.FTA,
                    MethodologyType.RCA_SYSTEMIC,
                    MethodologyType.BOWTIE,
                    MethodologyType.FIVE_WHY,  # 6-я
                ],
                incident=incident,
            )

    def test_duplicate_methodologies_rejected(self, incident):
        """Дубликат методики — ошибка валидации."""
        with pytest.raises(ValidationError):
            MultiAnalysisRequest(
                methodologies=[
                    MethodologyType.FIVE_WHY,
                    MethodologyType.FIVE_WHY,
                ],
                incident=incident,
            )

    def test_valid_2_methodologies(self, incident):
        """2 уникальные методики — проходит."""
        req = MultiAnalysisRequest(
            methodologies=[MethodologyType.FIVE_WHY, MethodologyType.ISHIKAWA],
            incident=incident,
        )
        assert len(req.methodologies) == 2

    def test_valid_5_methodologies(self, incident):
        """Все 5 методик — проходит."""
        req = MultiAnalysisRequest(
            methodologies=[
                MethodologyType.FIVE_WHY,
                MethodologyType.ISHIKAWA,
                MethodologyType.FTA,
                MethodologyType.RCA_SYSTEMIC,
                MethodologyType.BOWTIE,
            ],
            incident=incident,
        )
        assert len(req.methodologies) == 5


# ---------------------------------------------------------------------------
# 2. AnalysisService.compare() — логика сравнения
# ---------------------------------------------------------------------------

class TestCompareLogic:

    def test_compare_empty_raises(self):
        with pytest.raises(ValueError, match="Нет результатов"):
            AnalysisService.compare([])

    def test_compare_single_raises(self):
        r = _make_result(MethodologyType.FIVE_WHY)
        with pytest.raises(ValueError, match="минимум 2"):
            AnalysisService.compare([r])

    def test_compare_finds_common_recommendations(self):
        """Одинаковые рекомендации в двух методиках → common."""
        r1 = _make_result(MethodologyType.FIVE_WHY, rec_texts=["Ввести регламент уборки"])
        r2 = _make_result(MethodologyType.ISHIKAWA, rec_texts=["Ввести регламент по уборке"])
        result = AnalysisService.compare([r1, r2])
        assert len(result.common_recommendations) >= 1
        assert "регламент" in result.common_recommendations[0].text.lower()

    def test_compare_finds_no_common_when_different(self):
        """Разные рекомендации → common пустой."""
        r1 = _make_result(MethodologyType.FIVE_WHY, rec_texts=["Установить ограждения"])
        r2 = _make_result(MethodologyType.ISHIKAWA, rec_texts=["Провести обучение"])
        result = AnalysisService.compare([r1, r2])
        assert len(result.common_recommendations) == 0

    def test_compare_differing_causes_unique_only(self):
        """Уникальные причины — только уникальные для методики."""
        r1 = _make_result(MethodologyType.FIVE_WHY,
                          root_texts=["Нет регламента уборки", "Усталость работника"])
        r2 = _make_result(MethodologyType.ISHIKAWA,
                          root_texts=["Отсутствие регламента по уборке", "Низкая культура безопасности"])
        result = AnalysisService.compare([r1, r2])
        # "Нет регламента уборки" ~ "Отсутствие регламента по уборке" → общая
        # "Усталость работника" → уникальная для five_why
        # "Низкая культура безопасности" → уникальная для ishikawa
        assert "five_why" in result.differing_causes
        assert "ishikawa" in result.differing_causes
        assert any("Усталость" in c for c in result.differing_causes["five_why"])
        assert any("культура" in c for c in result.differing_causes["ishikawa"])

    def test_compare_summary_contains_info(self):
        """Сводка содержит информацию о методиках."""
        r1 = _make_result(MethodologyType.FIVE_WHY)
        r2 = _make_result(MethodologyType.ISHIKAWA)
        result = AnalysisService.compare([r1, r2])
        assert "2 методик" in result.summary

    def test_compare_3_methodologies(self):
        """Сравнение 3 методик работает корректно."""
        r1 = _make_result(MethodologyType.FIVE_WHY,
                          root_texts=["Нет регламента"],
                          rec_texts=["Ввести регламент"])
        r2 = _make_result(MethodologyType.ISHIKAWA,
                          root_texts=["Отсутствие регламента"],
                          rec_texts=["Разработать регламент"])
        r3 = _make_result(MethodologyType.FTA,
                          root_texts=["Поломка оборудования"],
                          rec_texts=["Заменить оборудование"])
        result = AnalysisService.compare([r1, r2, r3])
        # "Нет регламента" ~ "Отсутствие регламента" — общие для five_why и ishikawa
        assert len(result.common_recommendations) >= 1
        assert "fta" in result.differing_causes

    def test_compare_preserves_results(self):
        """Все исходные результаты сохранены."""
        r1 = _make_result(MethodologyType.FIVE_WHY)
        r2 = _make_result(MethodologyType.ISHIKAWA)
        result = AnalysisService.compare([r1, r2])
        assert len(result.results) == 2


# ---------------------------------------------------------------------------
# 3. _texts_are_similar — утилита нечёткого сравнения
# ---------------------------------------------------------------------------

class TestTextsAreSimilar:

    def test_identical(self):
        assert _texts_are_similar("Мокрый пол", "Мокрый пол")

    def test_similar_wording(self):
        assert _texts_are_similar("Нет регламента уборки", "Отсутствие регламента по уборке")

    def test_different(self):
        assert not _texts_are_similar("Мокрый пол", "Сломанная лестница")

    def test_case_insensitive(self):
        assert _texts_are_similar("Мокрый пол", "МОКРЫЙ ПОЛ")


# ---------------------------------------------------------------------------
# 4. Роут /analyze-multi — интеграционные тесты
# ---------------------------------------------------------------------------

from httpx import ASGITransport, AsyncClient  # noqa: E402

from src.api.app import app  # noqa: E402
from src.auth.models import UserInfo  # noqa: E402
from src.auth.service import get_current_user  # noqa: E402
from src.db.base import get_db  # noqa: E402


def _override_user(user: UserInfo):
    async def _dep() -> UserInfo:
        return user
    return _dep


def _override_db():
    async def _dep():
        yield AsyncMock()
    return _dep


@pytest.fixture
def mock_user() -> UserInfo:
    return UserInfo(user_id="test-user-001", email="test@test.com", display_name="Test User", role="user")


@pytest.fixture
def admin_user() -> UserInfo:
    return UserInfo(user_id="admin-001", email="admin@test.com", display_name="Admin", role="admin")


@pytest.fixture
async def async_client(mock_user):
    """Клиент с переопределёнными зависимостями (auth + db)."""
    app.dependency_overrides[get_db] = _override_db()
    app.dependency_overrides[get_current_user] = _override_user(mock_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def multi_payload() -> dict:
    return {
        "methodologies": ["five_why", "ishikawa"],
        "language": "ru",
        "detail_level": 2,
        "incident": {
            "title": "Падение с лестницы",
            "description": "Работник поскользнулся.",
            "incident_type": "injury",
            "severity": "moderate",
        },
    }


class TestAnalyzeMultiEndpoint:

    @pytest.mark.asyncio
    async def test_analyze_multi_success(self, async_client, multi_payload):
        mock_result = _make_result(MethodologyType.FIVE_WHY)
        with patch("src.api.routes.analyze._service") as mock_svc:
            mock_svc.analyze_multi = AsyncMock(return_value=[mock_result, mock_result])
            response = await async_client.post("/api/v1/analyze-multi", json=multi_payload)
        assert response.status_code == 201
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_analyze_multi_too_few(self, async_client, multi_payload):
        """Только 1 методика → 422."""
        multi_payload["methodologies"] = ["five_why"]
        response = await async_client.post("/api/v1/analyze-multi", json=multi_payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_multi_too_many(self, async_client, multi_payload):
        """6 методик → 422."""
        multi_payload["methodologies"] = [
            "five_why", "ishikawa", "fta", "rca_systemic", "bowtie", "five_why"
        ]
        response = await async_client.post("/api/v1/analyze-multi", json=multi_payload)
        # Дубликат тоже должен быть отловлен
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_multi_duplicates(self, async_client, multi_payload):
        """Дубликат методики → 422."""
        multi_payload["methodologies"] = ["five_why", "five_why"]
        response = await async_client.post("/api/v1/analyze-multi", json=multi_payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_multi_llm_error(self, async_client, multi_payload):
        from src.domain.models import LLMResponseValidationError
        with patch("src.api.routes.analyze._service") as mock_svc:
            mock_svc.analyze_multi = AsyncMock(
                side_effect=LLMResponseValidationError("bad json")
            )
            response = await async_client.post("/api/v1/analyze-multi", json=multi_payload)
        assert response.status_code == 502


class TestCompareEndpoint:

    @pytest.mark.asyncio
    async def test_compare_no_results_returns_400(self, admin_user):
        """Нет результатов для incident_id → 400."""
        app.dependency_overrides[get_db] = _override_db()
        app.dependency_overrides[get_current_user] = _override_user(admin_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
                mock_repo = AsyncMock()
                mock_repo.list_results = AsyncMock(return_value=[])
                MockRepo.return_value = mock_repo
                response = await client.get(
                    "/api/v1/results/compare?incident_id=inc-001"
                )

        app.dependency_overrides.clear()
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_compare_success(self, admin_user):
        """Сравнение результатов как admin."""
        r1 = _make_result(MethodologyType.FIVE_WHY)
        r2 = _make_result(MethodologyType.ISHIKAWA)

        app.dependency_overrides[get_db] = _override_db()
        app.dependency_overrides[get_current_user] = _override_user(admin_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
                mock_repo = AsyncMock()
                mock_repo.list_results = AsyncMock(return_value=[r1, r2])
                MockRepo.return_value = mock_repo
                response = await client.get(
                    "/api/v1/results/compare?incident_id=inc-test-001"
                )

        app.dependency_overrides.clear()
        assert response.status_code == 200
        data = response.json()
        assert data["incident_id"] == "inc-test-001"
        assert len(data["results"]) == 2
        assert "summary" in data
