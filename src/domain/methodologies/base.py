"""
Абстрактный базовый класс для методик RCA.

Любая новая методика должна:
1. Создать файл в src/domain/methodologies/<name>.py
2. Унаследоваться от MethodologyRunner
3. Реализовать метод run()
4. Добавить значение в MethodologyType (docs/contracts.md + models.py)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import AnalysisRequest, RCAResult

# Runners не знают финальный incident_id (UUID группы инцидента).
# Его назначает AnalysisService.analyze_multi() или API-роут после run().
UNASSIGNED_INCIDENT_ID = ""


class MethodologyRunner(ABC):
    """Базовый класс для всех методик анализа корневых причин."""

    @property
    @abstractmethod
    def methodology_type(self) -> str:
        """Возвращает MethodologyType, который обрабатывает этот runner."""
        ...

    @abstractmethod
    async def run(self, request: AnalysisRequest, raw_llm_response: dict) -> RCAResult:
        """
        Разобрать ответ LLM и сформировать RCAResult.

        Args:
            request: исходный запрос с данными об инциденте.
            raw_llm_response: уже провалидированный dict от LLM
                              (формат из docs/contracts.md раздел 6).

        Returns:
            Заполненный RCAResult.

        Raises:
            LLMResponseValidationError: если структура ответа нарушена.
        """
        ...

    def get_prompt_template_name(self) -> str:
        """
        Имя Jinja2-шаблона в configs/prompts/.
        По умолчанию совпадает с methodology_type.
        Переопределить, если имя файла отличается.
        """
        return f"{self.methodology_type}.j2"
