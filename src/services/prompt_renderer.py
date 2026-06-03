"""
Рендеринг промптов через Jinja2.

Конвенция шаблонов (configs/prompts/<methodology>.j2):

  Вариант A (простой, все существующие .j2):
    Весь шаблон — это user_prompt.
    system_prompt генерируется автоматически как "Метаданные методики".

  Вариант Б (расширенный, если нужна полная разделимость):
    {% block system %}системный промпт{% endblock %}
    {% block user %}пользовательский промпт{% endblock %}

Переменные, доступные в шаблоне:
    incident   — IncidentInput (все поля)
    request    — AnalysisRequest (methodology, language, detail_level)
Пример вызова:
    renderer = PromptRenderer()
    system, user = renderer.render("five_why.j2", request)
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError

from src.domain.models import AnalysisRequest

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "configs" / "prompts"

_AUTO_SYSTEM_TEMPLATE = (
    "You are an expert industrial safety analyst.\n"
    "Methodology: {methodology}. Language: {language}. Detail level: {detail_level}/3.\n"
    "Respond ONLY in {language_upper} language. Output strictly valid JSON."
)


class TemplateRenderError(Exception):
    """\u0414жинза сгенерировала ошибку при рендеринге."""


class PromptRenderer:
    """\u0420ендерит system + user промпт из Jinja2-\u0448аблона."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or _PROMPTS_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self._dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(
        self,
        template_name: str,
        request: AnalysisRequest,
    ) -> tuple[str, str]:
        """
        \u0420\u0435\u043d\u0434\u0435\u0440\u0438\u0442 \u0448\u0430\u0431\u043b\u043e\u043d \u0438 \u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u0442 (system_prompt, user_prompt).

        \u041b\u043e\u0433\u0438\u043a\u0430:
          1. \u0415\u0441\u043b\u0438 \u0448\u0430\u0431\u043b\u043e\u043d \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442 {% block system %} \u0438 {% block user %} \u2014 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u043c \u0438\u0445 (\u0432\u0430\u0440\u0438\u0430\u043d\u0442 \u0411).
          2. \u0418\u043d\u0430\u0447\u0435 \u2014 \u0432\u0435\u0441\u044c \u0448\u0430\u0431\u043b\u043e\u043d \u0438\u0434\u0451\u0442 \u043a\u0430\u043a user_prompt, \u0430 system_prompt \u0433\u0435\u043d\u0435\u0440\u0438\u0440\u0443\u0435\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 (\u0432\u0430\u0440\u0438\u0430\u043d\u0442 \u0410).

        Raises:
            FileNotFoundError: \u0448\u0430\u0431\u043b\u043e\u043d \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.
            TemplateRenderError: \u043e\u0448\u0438\u0431\u043a\u0430 \u0432 \u0448\u0430\u0431\u043b\u043e\u043d\u0435 (\u0441\u0438\u043d\u0442\u0430\u043a\u0441\u0438\u0441/\u043f\u0435\u0440\u0435\u043c\u0435\u043d\u043d\u0430\u044f).
        """
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(
                f"\u0428\u0430\u0431\u043b\u043e\u043d '{template_name}' \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0432 {self._dir}"
            ) from exc
        except TemplateSyntaxError as exc:
            raise TemplateRenderError(
                f"\u0421\u0438\u043d\u0442\u0430\u043a\u0441\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043e\u0448\u0438\u0431\u043a\u0430 \u0432 '{template_name}': {exc}"
            ) from exc

        ctx = {"incident": request.incident, "request": request}

        try:
            blocks = template.blocks
            has_system_block = "system" in blocks
            has_user_block   = "user"   in blocks

            if has_system_block and has_user_block:
                # \u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u0411: \u0448\u0430\u0431\u043b\u043e\u043d \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u044f\u0435\u0442 \u043e\u0431\u0430 \u0431\u043b\u043e\u043a\u0430
                rendered = template.render(**ctx)
                # \u0418\u0437\u0432\u043b\u0435\u043a\u0430\u0435\u043c \u0431\u043b\u043e\u043a\u0438 \u0447\u0435\u0440\u0435\u0437 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u044b\u0439 \u0440\u0435\u043d\u0434\u0435\u0440 \u0431\u043b\u043e\u043a\u043e\u0432
                system_prompt = "".join(
                    blocks["system"](template.new_context(ctx))
                ).strip()
                user_prompt = "".join(
                    blocks["user"](template.new_context(ctx))
                ).strip()
            else:
                # \u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u0410: \u0432\u0435\u0441\u044c \u0448\u0430\u0431\u043b\u043e\u043d \u2014 user_prompt
                user_prompt   = template.render(**ctx).strip()
                system_prompt = self._auto_system(request)

        except Exception as exc:
            if isinstance(exc, (FileNotFoundError, TemplateRenderError)):
                raise
            raise TemplateRenderError(
                f"\u041e\u0448\u0438\u0431\u043a\u0430 \u0440\u0435\u043d\u0434\u0435\u0440\u0438\u043d\u0433\u0430 '{template_name}': {exc}"
            ) from exc

        logger.debug(
            "[PromptRenderer] rendered '%s' | system=%d chars | user=%d chars",
            template_name,
            len(system_prompt),
            len(user_prompt),
        )

        return system_prompt, user_prompt

    # ------------------------------------------------------------------

    @staticmethod
    def _auto_system(request: AnalysisRequest) -> str:
        """\u0410\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u0441\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 system \u043f\u0440\u043e\u043c\u043f\u0442, \u0435\u0441\u043b\u0438 \u0432 \u0448\u0430\u0431\u043b\u043e\u043d\u0435 \u043d\u0435\u0442 {% block system %}."""
        return _AUTO_SYSTEM_TEMPLATE.format(
            methodology=request.methodology.value,
            language=request.language,
            language_upper=request.language.upper(),
            detail_level=request.detail_level,
        )

    def list_templates(self) -> list[str]:
        """\u0412\u0435\u0440\u043d\u0443\u0442\u044c \u0441\u043f\u0438\u0441\u043e\u043a \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u0448\u0430\u0431\u043b\u043e\u043d\u043e\u0432."""
        return self._env.loader.list_templates()  # type: ignore[union-attr]
