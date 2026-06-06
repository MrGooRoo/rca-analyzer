"""
Сервис извлечения структурированных полей инцидента из текста отчёта через LLM.

Поток:
  raw text (из DOCX) → LLM prompt → JSON с полями IncidentInput
"""

from __future__ import annotations

import json
import logging

from src.integrations.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Максимум символов текста отчёта, отправляемых в LLM (защита от огромных файлов)
MAX_TEXT_LENGTH = 15_000

SYSTEM_PROMPT = """\
Ты — специалист по анализу отчётов об инцидентах на производстве.
Твоя задача: прочитать текст отчёта и извлечь из него структурированную информацию.

Верни СТРОГО JSON-объект со следующими полями:

{
  "title": "Краткий заголовок инцидента (до 100 символов)",
  "description": "Подробное описание инцидента — что произошло, обстоятельства, хронология",
  "incident_date": "Дата и время в формате YYYY-MM-DDTHH:MM:SS (если время неизвестно — 00:00:00)",
  "location": "Место инцидента",
  "incident_type": "Тип: одно из injury|equipment|fire|spill|near_miss|process_upset|security|environmental",
  "severity": "Тяжесть: одно из critical|major|moderate|minor|near_miss",
  "victims": 0,
  "equipment": "Оборудование, если упоминается (или null)",
  "conditions": "Условия, способствовавшие инциденту (или null)",
  "actions_taken": "Принятые меры / немедленные действия (или null)"
}

Правила:
- Если какое-то поле невозможно определить из текста, используй разумное значение по умолчанию.
- incident_type и severity — СТРОГО одно из перечисленных значений.
- victims — целое число (0 если не указано).
- Не добавляй никаких полей кроме перечисленных.
- Ответ — ТОЛЬКО JSON, без markdown, без пояснений.\
"""

USER_PROMPT_TEMPLATE = """\
Проанализируй следующий текст отчёта об инциденте и извлеки структурированные данные.

--- ТЕКСТ ОТЧЁТА ---
{report_text}
--- КОНЕЦ ОТЧЁТА ---

Верни JSON с полями: title, description, incident_date, location, incident_type, severity, victims, equipment, conditions, actions_taken.\
"""


async def extract_fields_from_text(report_text: str) -> dict:
    """
    Отправить текст отчёта в LLM и получить структурированные поля инцидента.

    Returns:
        dict с полями IncidentInput (title, description, incident_date, ...)

    Raises:
        LLMResponseValidationError — если LLM не вернул валидный JSON.
        ValueError — если текст отчёта пустой.
    """
    if not report_text or not report_text.strip():
        raise ValueError("Текст отчёта пустой — невозможно извлечь данные.")

    # Обрезаем слишком длинный текст
    trimmed = report_text[:MAX_TEXT_LENGTH]
    if len(report_text) > MAX_TEXT_LENGTH:
        logger.warning(
            "[DocxFields] Текст обрезан: %d → %d символов",
            len(report_text),
            MAX_TEXT_LENGTH,
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(report_text=trimmed)

    async with OpenRouterClient() as client:
        raw = await client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=2048,
        )

    # Убираем служебный ключ _meta из ответа LLM
    raw.pop("_meta", None)

    # Валидация и нормализация полей
    fields = _normalize_fields(raw)

    logger.info(
        "[DocxFields] Извлечены поля: title=%s, type=%s, severity=%s",
        fields.get("title", "")[:50],
        fields.get("incident_type"),
        fields.get("severity"),
    )

    return fields


VALID_TYPES = {
    "injury", "equipment", "fire", "spill",
    "near_miss", "process_upset", "security", "environmental",
}
VALID_SEVERITIES = {"critical", "major", "moderate", "minor", "near_miss"}


def _normalize_fields(raw: dict) -> dict:
    """Привести поля к допустимым значениям, заполнить пропуски дефолтами."""
    fields: dict = {}

    fields["title"] = str(raw.get("title", "Инцидент (из отчёта)"))[:200]
    fields["description"] = str(raw.get("description", ""))
    fields["incident_date"] = str(raw.get("incident_date", ""))
    fields["location"] = str(raw.get("location", ""))

    # incident_type
    it = str(raw.get("incident_type", "")).lower().strip()
    fields["incident_type"] = it if it in VALID_TYPES else "process_upset"

    # severity
    sev = str(raw.get("severity", "")).lower().strip()
    fields["severity"] = sev if sev in VALID_SEVERITIES else "moderate"

    # victims
    try:
        fields["victims"] = max(0, int(raw.get("victims", 0)))
    except (ValueError, TypeError):
        fields["victims"] = 0

    # Optional fields
    for key in ("equipment", "conditions", "actions_taken"):
        val = raw.get(key)
        fields[key] = str(val) if val and str(val).lower() != "null" else None

    return fields
