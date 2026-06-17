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
    detail_map — dict {1: "кратко", 2: "стандартно", 3: "подробно"}
Пример вызова:
    renderer = PromptRenderer()
    system, user = renderer.render("five_why.j2", request)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError

from src.domain.models import AnalysisRequest

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "configs" / "prompts"

_AUTO_SYSTEM_TEMPLATE = (
    "You are an expert industrial safety analyst.\n"
    "Methodology: {methodology}. Language: {language}. Detail level: {detail_level}/3.\n"
    "Respond ONLY in {language_upper} language. Output strictly valid JSON."
)

_DETAIL_MAP = {
    1: "кратко (1–2 абзаца)",
    2: "стандартно (3–5 абзацев)",
    3: "подробно (полный разбор)",
}


class TemplateRenderError(Exception):
    """Джинза сгенерировала ошибку при рендеринге."""


class PromptRenderer:
    """Рендерит system + user промпт из Jinja2-шаблона."""

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
        extra_context: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Рендерит шаблон и возвращает (system_prompt, user_prompt).

        Логика:
          1. Если шаблон содержит {% block system %} и {% block user %} — используем их (вариант Б).
          2. Иначе — весь шаблон идёт как user_prompt, а system_prompt генерируется автоматически (вариант А).

        Raises:
            FileNotFoundError: шаблон не найден.
            TemplateRenderError: ошибка в шаблоне (синтаксис/переменная).
        """
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(
                f"Шаблон '{template_name}' не найден в {self._dir}"
            ) from exc
        except TemplateSyntaxError as exc:
            raise TemplateRenderError(
                f"Синтаксическая ошибка в '{template_name}': {exc}"
            ) from exc

        ctx = {
            "incident": request.incident,
            "request": request,
            "detail_map": _DETAIL_MAP,
        }
        if extra_context:
            ctx.update(extra_context)

        try:
            blocks = template.blocks
            has_system_block = "system" in blocks
            has_user_block   = "user"   in blocks

            if has_system_block and has_user_block:
                # Вариант Б: шаблон определяет оба блока
                system_prompt = "".join(
                    blocks["system"](template.new_context(ctx))
                ).strip()
                user_prompt = "".join(
                    blocks["user"](template.new_context(ctx))
                ).strip()
            else:
                # Вариант А: весь шаблон — user_prompt
                user_prompt   = template.render(**ctx).strip()
                system_prompt = self._auto_system(request)

        except Exception as exc:
            if isinstance(exc, (FileNotFoundError, TemplateRenderError)):
                raise
            raise TemplateRenderError(
                f"Ошибка рендеринга '{template_name}': {exc}"
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
        """Автоматически сгенерированный system промпт, если в шаблоне нет {% block system %}."""
        return _AUTO_SYSTEM_TEMPLATE.format(
            methodology=request.methodology.value,
            language=request.language,
            language_upper=request.language.upper(),
            detail_level=request.detail_level,
        )

    def list_templates(self) -> list[str]:
        """Вернуть список доступных шаблонов."""
        return self._env.loader.list_templates()  # type: ignore[union-attr]
