"""
\u0422\u0435\u0441\u0442\u044b PromptRenderer.
\u0417\u0430\u043f\u0443\u0441\u043a: pytest tests/unit/test_prompt_renderer.py
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.domain.models import AnalysisRequest, IncidentInput, MethodologyType
from src.services.prompt_renderer import PromptRenderer


@pytest.fixture
def tmp_prompts(tmp_path: Path) -> Path:
    """\u0412\u0440\u0435\u043c\u0435\u043d\u043d\u0430\u044f \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0438\u044f \u0441 \u0442\u0435\u0441\u0442\u043e\u0432\u044b\u043c\u0438 .j2 \u0448\u0430\u0431\u043b\u043e\u043d\u0430\u043c\u0438."""
    # \u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u0410: \u043f\u043b\u043e\u0441\u043a\u0438\u0439 \u0448\u0430\u0431\u043b\u043e\u043d (user-only)
    (tmp_path / "flat.j2").write_text(
        "Analyse incident: {{ request.incident.title }}. Method: {{ request.methodology.value }}.",
        encoding="utf-8",
    )
    # \u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u0411: \u0448\u0430\u0431\u043b\u043e\u043d \u0441 \u0431\u043b\u043e\u043a\u0430\u043c\u0438
    (tmp_path / "blocks.j2").write_text(
        "{% block system %}You are a safety expert.{% endblock %}\n"
        "{% block user %}Incident: {{ request.incident.title }}{% endblock %}",
        encoding="utf-8",
    )
    # \u041f\u0443\u0441\u0442\u043e\u0439 \u0448\u0430\u0431\u043b\u043e\u043d
    (tmp_path / "empty.j2").write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture
def renderer(tmp_prompts: Path) -> PromptRenderer:
    return PromptRenderer(prompts_dir=tmp_prompts)


@pytest.fixture
def req() -> AnalysisRequest:
    return AnalysisRequest(
        incident=IncidentInput(
            title="\u041f\u0430\u0434\u0435\u043d\u0438\u0435 \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435",
            description="\u0420\u0430\u0431\u043e\u0447\u0438\u0439 \u0443\u043f\u0430\u043b \u0441 \u0432\u044b\u0441\u043e\u0442\u044b 3 \u043c\u0435\u0442\u0440\u0430 \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0441\u043a\u0438\u0445 \u043b\u0435\u0441\u0430\u0445.",
            incident_date=datetime(2026, 1, 15, 10, 0),
            location="\u0421\u043a\u043b\u0430\u0434 \u21161",
            incident_type="injury",
            severity="major",
        ),
        methodology=MethodologyType.FIVE_WHY,
        language="ru",
        detail_level=2,
    )


class TestPromptRenderer:
    def test_flat_template_returns_auto_system(self, renderer, req):
        system, user = renderer.render("flat.j2", req)
        assert "five_why" in system
        assert "ru" in system.lower() or "RU" in system
        assert "\u041f\u0430\u0434\u0435\u043d\u0438\u0435" in user

    def test_flat_template_user_contains_rendered_content(self, renderer, req):
        _, user = renderer.render("flat.j2", req)
        assert "five_why" in user
        assert "\u041f\u0430\u0434\u0435\u043d\u0438\u0435 \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435" in user

    def test_blocks_template_uses_explicit_system(self, renderer, req):
        system, user = renderer.render("blocks.j2", req)
        assert system == "You are a safety expert."
        assert "\u041f\u0430\u0434\u0435\u043d\u0438\u0435" in user

    def test_blocks_template_user_contains_incident(self, renderer, req):
        _, user = renderer.render("blocks.j2", req)
        assert "\u041f\u0430\u0434\u0435\u043d\u0438\u0435 \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435" in user

    def test_empty_template_returns_auto_system_and_empty_user(self, renderer, req):
        system, user = renderer.render("empty.j2", req)
        assert "five_why" in system
        assert user == ""

    def test_missing_template_raises_file_not_found(self, renderer, req):
        with pytest.raises(FileNotFoundError, match="nonexistent.j2"):
            renderer.render("nonexistent.j2", req)

    def test_list_templates_returns_j2_files(self, renderer):
        templates = renderer.list_templates()
        assert "flat.j2" in templates
        assert "blocks.j2" in templates

    def test_auto_system_contains_detail_level(self, renderer, req):
        system, _ = renderer.render("flat.j2", req)
        assert str(req.detail_level) in system
