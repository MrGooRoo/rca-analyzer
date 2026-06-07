
"""
Сервис извлечения структурированных полей инцидента из текста отчёта через LLM.
"""

from __future__ import annotations

import logging

from src.integrations.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Стратегия head + tail + section-aware:
#   * head  — начало документа (обзор, пострадавшие, даты);
#   * tail  — конец документа (часто там выводы/заключение);
#   * section slices — целевые срезы вокруг ключевых разделов
#     («Установленные факты», «Обстоятельства», «Причины» и т.д.),
#     чтобы они не терялись в «мёртвой зоне» между head и tail
#     в очень длинных документах (>16 000 символов).
HEAD_CHUNK = 10_000
TAIL_CHUNK = 10_000

# Сколько символов захватывать вокруг найденного заголовка раздела.
# Заголовок может быть в любом месте документа; берём весь раздел целиком
# (до следующего известного заголовка или до SECTION_WINDOW символов).
SECTION_WINDOW = 14_000

# Ключевые заголовки разделов, которые ОБЯЗАТЕЛЬНО должны попасть в срез.
# Сопоставление регистронезависимое, по вхождению подстроки в строку-начало абзаца.
SECTION_KEYWORDS: tuple[str, ...] = (
    "установленные факты",
    "установленные обстоятельства",
    "обстоятельства несчастного случая",
    "обстоятельства происшествия",
    "обстоятельства и причины",
    "причины несчастного случая",
    "причины происшествия",
    "причины инцидента",
    "сведения о пострадавш",
    "лица, допустившие нарушения",
    "мероприятия по устранению",
    "описание места происшествия",
    "характеристика оборудования",
    "характеристика объекта",
    "основная причина",
    "выводы",
    "заключение",
    "рекомендации",
    "принятые меры",
    "дополнительные сведения",
    "акт расследования",
    "акт о несчастном случае",
    "результаты расследования",
)

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
- НЕ сокращай и НЕ обрезай значения полей — извлекай полный текст из отчёта.
- Для established_facts, full_circumstances, scene_description, equipment_description и description сохраняй максимально полный текст (до 3000 символов на поле).
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


def _find_section_spans(text: str) -> list[tuple[int, int]]:
    """Находит позиции ключевых разделов в тексте.

    Для каждого найденного заголовка раздела захватывает текст
    либо до следующего известного заголовка, либо до SECTION_WINDOW
    символов — что больше (чтобы не обрезать длинные разделы).
    Регистронезависимый поиск по вхождению ключевых слов.
    """
    lowered = text.lower()
    n = len(text)

    # Собираем все позиции всех ключевых слов
    positions: list[tuple[int, str]] = []  # (индекс, ключевое_слово)
    for kw in SECTION_KEYWORDS:
        start = 0
        while True:
            idx = lowered.find(kw, start)
            if idx == -1:
                break
            positions.append((idx, kw))
            start = idx + len(kw)

    if not positions:
        return []

    positions.sort()

    spans: list[tuple[int, int]] = []
    for i, (pos, _kw) in enumerate(positions):
        # Конец раздела: либо позиция следующего заголовка, либо SECTION_WINDOW
        # Используем max, чтобы гарантированно захватить SECTION_WINDOW минимум
        if i + 1 < len(positions):
            next_pos = positions[i + 1][0]
            end = max(pos + SECTION_WINDOW, next_pos)
        else:
            end = pos + SECTION_WINDOW
        end = min(end, n)
        spans.append((pos, end))

    return spans


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Сливает пересекающиеся/смежные диапазоны в упорядоченный список."""
    if not spans:
        return []
    spans = sorted(spans)
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _trim_text(text: str) -> tuple[str, bool]:
    """Возвращает (trimmed_text, was_trimmed).

    Стратегия для длинных документов (> HEAD_CHUNK + TAIL_CHUNK):
      1. Берём head (начало) и tail (конец).
      2. Дополнительно ищем ключевые разделы по всему документу
         («Установленные факты» и т.п.) и принудительно включаем
         их срезы, даже если они находятся в середине.
      3. Все диапазоны сливаются и склеиваются по порядку с метками
         о пропущенных фрагментах.

    Так раздел «Установленные факты» гарантированно попадёт в срез
    независимо от его положения в документе.
    """
    total = HEAD_CHUNK + TAIL_CHUNK  # 20 000 — не обрезаем короткие документы
    if len(text) <= total:
        return text, False

    n = len(text)
    spans: list[tuple[int, int]] = [(0, HEAD_CHUNK), (n - TAIL_CHUNK, n)]
    spans.extend(_find_section_spans(text))
    merged = _merge_spans(spans)

    parts: list[str] = []
    prev_end = 0
    for start, end in merged:
        if start > prev_end:
            parts.append(f"\n...[пропущено {start - prev_end} символов]...\n")
        parts.append(text[start:end])
        prev_end = end
    if prev_end < n:
        parts.append(f"\n...[пропущено {n - prev_end} символов]...\n")

    trimmed = "".join(parts)
    return trimmed, True


async def extract_fields_from_text(report_text: str) -> dict:
    if not report_text or not report_text.strip():
        raise ValueError("Текст отчёта пустой — невозможно извлечь данные.")

    trimmed, was_trimmed = _trim_text(report_text)
    if was_trimmed:
        logger.warning(
            "[DocxFields] Текст обрезан (head+tail): %d → %d символов",
            len(report_text),
            len(trimmed),
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(report_text=trimmed)

    async with OpenRouterClient() as client:
        raw = await client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=8192,
            # upload использует свою схему — не требуем summary/recommendations
            required_keys={"title"},
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
