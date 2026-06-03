"""
Рендеринг промптов через Jinja2.

Шаблоны лежат в configs/prompts/<methodology>.j2
Каждый шаблон должен определять два блока:
    {% block system %}...{% endblock %}
    {% block user %}...{% endblock %}

Переменные, доступные в шаблоне:
    incident   — IncidentInput (все поля)
    request    — AnalysisRequest (methodology, language, detail_level)

Пример вызова:
    renderer = PromptRenderer()
    system, user = renderer.render("five_why.j2", request)
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from src.domain.models import AnalysisRequest

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "configs" / "prompts"


class PromptRenderer:
    """Рендерит system + user промпт из Jinja2-шаблона."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or _PROMPTS_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self._dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template_name: str,
        request: AnalysisRequest,
    ) -> tuple[str, str]:
        """
        Рендерит шаблон и возвращает (system_prompt, user_prompt).

        Raises:
            FileNotFoundError: если шаблон не найден в configs/prompts/.
        """
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(
                f"Шаблон '{template_name}' не найден в {self._dir}"
            ) from exc

        ctx = {
            "incident": request.incident,
            "request":  request,
        }

        system = template.module.system(**ctx) if hasattr(template.module, "system") else ""
        user   = template.module.user(**ctx)   if hasattr(template.module, "user")   else ""

        # Fallback: весь шаблон → user prompt
        if not system and not user:
            rendered = template.render(**ctx)
            return "", rendered

        return system.strip(), user.strip()
