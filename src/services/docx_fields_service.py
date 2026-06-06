"""
Сервис извлечения структурированных полей инцидента из текста отчёта через LLM.
"""

from __future__ import annotations

import logging

from src.integrations.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 15_000

SYSTEM_PROMPT = """\
Ты — специалист по анализу отчётов об инцидентах на производстве.
Твоя задача: прочитать текст отчёта и извлечь из него структурированную информацию.

Верни СТРОГО JSON-объект со следующими полями (все поля на верхнем уровне):

{
  "title": "Краткий заголовок инцидента",
  "description": "Подробное описание инцидента",
  "incident_date": "Дата в формате YYYY-MM-DD (если неизвестна — null)",
  "incident_time": "Время в формате HH:MM (если неизвестно — null)",
  "company": "Название компании",
  "department": "Подразделение",
  "location": "Место происшествия",
  "injured_count": число пострадавших,
  "fatalities_count": число погибших,
  "short_description": "Краткое описание",
  "incident_type": "Тип: injury|equipment|fire|spill|near_miss|process_upset|security|environmental",
  "severity": "Тяжесть: critical|major|moderate|minor|near_miss",
  "equipment": "Оборудование (или null)",
  "conditions": "Условия (или null)",
  "actions_taken": "Принятые меры (или null)",
  "scene_description": "Описание места происшествия",
  "equipment_description": "Характеристика оборудования/объекта",
  "full_circumstances": "Полное описание обстоятельств происшествия",
  "established_facts": "Установленные факты",
  "victims_list": [ массив объектов Victim — см. ниже ]
}

Структура объекта Victim:
{
  "full_name": "ФИО",
  "birth_date": "YYYY-MM-DD или null",
  "age": число или null,
  "family_status": "семейное положение",
  "children_under_21": число,
  "profession": "профессия/должность",
  "workplace": "место работы",
  "total_experience": "общий стаж",
  "experience_in_organization": "стаж в организации",
  "qualification_certificate": "квалификационное удостоверение",
  "introductory_briefing": "вводный инструктаж",
  "workplace_briefing": "инструктаж на рабочем месте",
  "internship": "стажировка/допуск",
  "safety_knowledge_test": "проверка знаний",
  "medical_examination": "медосмотр",
  "diagnosis_severity": "диагноз / степень тяжести"
}

Правила:
- Если поле невозможно определить — используй null.
- victims_list может быть пустым массивом.
- incident_type и severity — строго из перечисленных значений.
- Ответ — ТОЛЬКО JSON, без markdown.\
"""

USER_PROMPT_TEMPLATE = """\
Проанализируй следующий текст отчёта об инциденте и извлеки структурированные данные.

--- ТЕКСТ ОТЧЁТА ---
{report_text}
--- КОНЕЦ ОТЧЁТА ---

Верни JSON со всеми полями из схемы (включая victims_list, scene_description и т.д.).\
"""


async def extract_fields_from_text(report_text: str) -> dict:
    if not report_text or not report_text.strip():
        raise ValueError("Текст отчёта пустой — невозможно извлечь данные.")

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
            max_tokens=3000,
        )

    raw.pop("_meta", None)
    fields = _normalize_fields(raw)

    logger.info(
        "[DocxFields] Извлечены поля: title=%s",
        fields.get("title", "")[:50],
    )

    return fields


VALID_TYPES = {
    "injury", "equipment", "fire", "spill",
    "near_miss", "process_upset", "security", "environmental",
}
VALID_SEVERITIES = {"critical", "major", "moderate", "minor", "near_miss"}


def _normalize_fields(raw: dict) -> dict:
    fields: dict = {}

    fields["title"] = str(raw.get("title", "Инцидент (из отчёта)"))[:200]
    fields["description"] = str(raw.get("description", ""))
    fields["incident_date"] = str(raw.get("incident_date", "")) or None
    fields["incident_time"] = str(raw.get("incident_time", "")) or None
    fields["company"] = str(raw.get("company", "")) or None
    fields["department"] = str(raw.get("department", "")) or None
    fields["location"] = str(raw.get("location", ""))
    fields["injured_count"] = int(raw.get("injured_count", 0)) or None
    fields["fatalities_count"] = int(raw.get("fatalities_count", 0)) or None
    fields["short_description"] = str(raw.get("short_description", "")) or None

    it = str(raw.get("incident_type", "")).lower().strip()
    fields["incident_type"] = it if it in VALID_TYPES else "process_upset"

    sev = str(raw.get("severity", "")).lower().strip()
    fields["severity"] = sev if sev in VALID_SEVERITIES else "moderate"

    for key in ("equipment", "conditions", "actions_taken",
                "scene_description", "equipment_description",
                "full_circumstances", "established_facts"):
        val = raw.get(key)
        fields[key] = str(val) if val and str(val).lower() != "null" else None

    victims_raw = raw.get("victims_list", [])
    fields["victims_list"] = victims_raw if isinstance(victims_raw, list) else []

    return fields