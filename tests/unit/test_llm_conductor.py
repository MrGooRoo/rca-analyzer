"""Unit tests for P17 LLMConductor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from src.domain.methodologies.five_why import FiveWhyRunner
from src.domain.models import AnalysisRequest, IncidentInput, LLMSettings, MethodologyType
from src.services.llm_conductor import LLMConductor


@pytest.fixture
def request_obj() -> AnalysisRequest:
    return AnalysisRequest(
        incident=IncidentInput(
            title="Падение работника с лестницы",
            description="Работник поскользнулся на мокрой ступени и упал с высоты 2 м.",
            incident_date=datetime(2026, 6, 1, 9, 30),
            location="Цех №3",
            incident_type="injury",
            severity="moderate",
        ),
        methodology=MethodologyType.FIVE_WHY,
        language="ru",
        detail_level=2,
    )


def _raw_result(*, summary: str, confidence: float, model: str, tokens: int) -> dict[str, Any]:
    return {
        "immediate_causes": [
            {
                "id": "n1",
                "text": "Работник поскользнулся на мокрой ступени",
                "category": "среда",
                "level": 0,
                "parent_id": None,
                "confidence": confidence,
            }
        ],
        "contributing_causes": [
            {
                "id": "n2",
                "text": "Мокрая ступень не была своевременно очищена",
                "category": "процесс",
                "level": 1,
                "parent_id": "n1",
                "confidence": confidence,
            }
        ],
        "root_causes": [
            {
                "id": "n3",
                "text": "Недостаточный контроль порядка уборки и осмотра лестниц",
                "category": "управление",
                "level": 2,
                "parent_id": "n2",
                "confidence": confidence,
            }
        ],
        "summary": summary,
        "recommendations": [
            {
                "id": "r1",
                "text": "Ввести регулярный осмотр и очистку лестниц",
                "priority": "high",
                "category": "systemic",
                "cause_id": "n3",
                "responsible": "Служба эксплуатации",
            }
        ],
        "_meta": {"model": model, "tokens": tokens},
    }


class _FakeLLM:
    def __init__(self, responses: list[dict[str, Any]], calls: list[dict[str, Any]], **kwargs):
        self._responses = responses
        self._calls = calls
        self._kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def complete(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self._calls.append(
            {
                "model": self._kwargs.get("model"),
                "fallback_models": self._kwargs.get("fallback_models"),
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "complete_kwargs": kwargs,
            }
        )
        return self._responses.pop(0)


def _factory(responses: list[dict[str, Any]], calls: list[dict[str, Any]]):
    def _make(**kwargs):
        return _FakeLLM(responses, calls, **kwargs)

    return _make


@pytest.mark.asyncio
async def test_conductor_disabled_scheme_uses_only_draft(request_obj):
    responses = [_raw_result(summary="Черновик достаточен", confidence=0.4, model="draft-model", tokens=100)]
    calls: list[dict[str, Any]] = []
    settings = LLMSettings(
        draft_model="draft-model",
        verifier_model=None,
        quality_threshold=0.7,
        verification_scheme="disabled",
    )

    result = await LLMConductor(settings, llm_factory=_factory(responses, calls)).analyze(
        request_obj,
        FiveWhyRunner(),
    )

    assert result.summary == "Черновик достаточен"
    assert result.model_used == "draft-model"
    assert result.tokens_used == 100
    assert len(calls) == 1
    assert calls[0]["model"] == "draft-model"
    assert calls[0]["fallback_models"] == []


@pytest.mark.asyncio
async def test_conductor_threshold_skips_verifier_for_high_confidence(request_obj):
    responses = [_raw_result(summary="Высокая уверенность", confidence=0.82, model="draft-model", tokens=120)]
    calls: list[dict[str, Any]] = []
    settings = LLMSettings(
        draft_model="draft-model",
        verifier_model="verifier-model",
        quality_threshold=0.7,
        verification_scheme="threshold",
    )

    result = await LLMConductor(settings, llm_factory=_factory(responses, calls)).analyze(
        request_obj,
        FiveWhyRunner(),
    )

    assert result.summary == "Высокая уверенность"
    assert result.confidence_avg == 0.82
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_conductor_threshold_runs_verifier_for_low_confidence(request_obj):
    responses = [
        _raw_result(summary="Черновой вывод", confidence=0.45, model="draft-model", tokens=100),
        _raw_result(summary="Проверенный вывод", confidence=0.86, model="verifier-model", tokens=35),
    ]
    calls: list[dict[str, Any]] = []
    settings = LLMSettings(
        draft_model="draft-model",
        verifier_model="verifier-model",
        quality_threshold=0.7,
        verification_scheme="threshold",
    )

    result = await LLMConductor(settings, llm_factory=_factory(responses, calls)).analyze(
        request_obj,
        FiveWhyRunner(),
    )

    assert result.summary == "Проверенный вывод"
    assert result.model_used == "draft-model -> verifier-model"
    assert result.tokens_used == 135
    assert len(calls) == 2
    assert calls[0]["model"] == "draft-model"
    assert calls[1]["model"] == "verifier-model"
    assert "Черновой вывод" in calls[1]["user_prompt"]
    assert "Недостаточный контроль порядка уборки" in calls[1]["user_prompt"]
    assert "immediate_causes" in calls[1]["user_prompt"]


@pytest.mark.asyncio
async def test_conductor_always_runs_verifier_even_for_high_confidence(request_obj):
    responses = [
        _raw_result(summary="Черновой вывод", confidence=0.95, model="draft-model", tokens=90),
        _raw_result(summary="Проверенный вывод", confidence=0.96, model="verifier-model", tokens=30),
    ]
    calls: list[dict[str, Any]] = []
    settings = LLMSettings(
        draft_model="draft-model",
        verifier_model="verifier-model",
        quality_threshold=0.7,
        verification_scheme="always",
    )

    result = await LLMConductor(settings, llm_factory=_factory(responses, calls)).analyze(
        request_obj,
        FiveWhyRunner(),
    )

    assert result.summary == "Проверенный вывод"
    assert result.tokens_used == 120
    assert len(calls) == 2
