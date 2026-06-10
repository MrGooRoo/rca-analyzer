"""
Сервис извлечения структурированных полей инцидента из текста отчёта через LLM.
"""

from __future__ import annotations

import logging

from src.integrations.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

_LARGE_CONTEXT_THRESHOLD_TOKENS = 200_000

_KNOWN_MODEL_CONTEXTS: dict[str, int] = {
    "nemotron-3-ultra":   1_000_000,
    "nemotron-3-super":   1_000_000,
    "nemotron-3-nano":      256_000,
    "qwen3-next":           262_144,
    "qwen3-coder":        1_048_576,
    "gemma-4":              262_144,
    "kimi":                 262_144,
    "laguna":               262_144,
    "openrouter/owl":     1_048_756,
    "openrouter/free":      200_000,
    "lyria":              1_048_576,
    "llama-3.3-70b":        131_072,
    "gpt-oss-120b":         131_072,
    "gpt-oss-20b":          131_072,
    "hermes-3-llama-3.1-405b": 131_072,
}


def _get_model_context_limit() -> int:
    from os import getenv
    explicit = getenv("OPENROUTER_MODEL_MAX_CONTEXT")
    if explicit:
        try:
            return int(explicit)
        except ValueError:
            logger.warning(
                "[DocxFields] Некорректный OPENROUTER_MODEL_MAX_CONTEXT=%s — "
                "использую автоопределение",
                explicit,
            )
    model_id = getenv("OPENROUTER_MODEL", "").lower()
    for key, ctx in _KNOWN_MODEL_CONTEXTS.items():
        if key in model_id:
            return ctx
    return 131_072


def _model_supports_full_text(model_ctx_tokens: int) -> bool:
    return model_ctx_tokens >= _LARGE_CONTEXT_THRESHOLD_TOKENS


_DEFAULT_MAX_INPUT_CHARS = 20_000


def _get_max_input_chars() -> int:
    from os import getenv
    val = getenv("DOCX_MAX_INPUT_CHARS")
    if val:
        try:
            return int(val)
        except ValueError:
            logger.warning("[DocxFields] Некорректный DOCX_MAX_INPUT_CHARS=%s", val)
    return _DEFAULT_MAX_INPUT_CHARS


HEAD_CHUNK = 10_000
TAIL_CHUNK = 10_000
SECTION_WINDOW = 14_000

SECTION_KEYWORDS: tuple[str, ...] = (
    "установленные факты",
    "комиссией установлено",
    "в ходе расследования установлено",
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
- НЕ перефразируй и НЕ сокращай текст для полей description, scene_description, equipment_description, full_circumstances, established_facts.
- Извлекай их ДОСЛОВНО (прямым копированием из текста), сохраняя все абзацы, списки и маркированные пункты целиком.
- В разделе "Установленные факты" ("established_facts") часто содержатся длинные списки или хронологии — обязательно извлеки их ПОЛНОСТЬЮ, без потери пунктов.
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
    lowered = text.lower()
    n = len(text)
    positions: list[tuple[int, str]] = []
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
        if i + 1 < len(positions):
            next_pos = positions[i + 1][0]
            end = max(pos + SECTION_WINDOW, next_pos)
        else:
            end = pos + SECTION_WINDOW
        end = min(end, n)
        spans.append((pos, end))
    return spans


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
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


def _trim_text(text: str, max_input_chars: int | None = None) -> tuple[str, bool]:
    if max_input_chars is None:
        max_input_chars = _get_max_input_chars()
    if len(text) <= max_input_chars:
        return text, False
    n = len(text)
    head_sz = min(HEAD_CHUNK, max_input_chars // 2)
    tail_sz = min(TAIL_CHUNK, max_input_chars // 2)
    spans: list[tuple[int, int]] = [(0, head_sz), (n - tail_sz, n)]
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

    model_ctx = _get_model_context_limit()
    full_text_ok = _model_supports_full_text(model_ctx)

    if full_text_ok:
        trimmed = report_text
        was_trimmed = False
        logger.info(
            "[DocxFields] Модель с контекстом %d токенов — "
            "отправляю полный текст (%d символов) без обрезки",
            model_ctx,
            len(report_text),
        )
    else:
        max_chars = _get_max_input_chars()
        trimmed, was_trimmed = _trim_text(report_text, max_input_chars=max_chars)
        if was_trimmed:
            logger.warning(
                "[DocxFields] Текст обрезан (контекст модели %d токенов): "
                "%d → %d символов",
                model_ctx, len(report_text), len(trimmed),
            )
        else:
            logger.info(
                "[DocxFields] Текст уместился в лимит %d символов, не обрезан",
                max_chars,
            )

    user_prompt = USER_PROMPT_TEMPLATE.format(report_text=trimmed)

    # Первая попытка: полный текст, большой лимит токенов
    response_tokens = 32768 if full_text_ok else 8192

    try:
        async with OpenRouterClient() as client:
            raw = await client.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=response_tokens,
                required_keys={"title"},
            )
    except Exception as exc:
        if full_text_ok and not was_trimmed:
            # Fallback: повторить с обрезанным текстом
            logger.warning(
                "[DocxFields] Полный текст не сработал (%s). "
                "Повторяю с обрезанным текстом.",
                exc,
            )
            max_chars = _get_max_input_chars()
            trimmed_fallback, _ = _trim_text(report_text, max_input_chars=max_chars)
            user_prompt_fallback = USER_PROMPT_TEMPLATE.format(report_text=trimmed_fallback)
            async with OpenRouterClient() as client2:
                raw = await client2.complete(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt_fallback,
                    temperature=0.1,
                    max_tokens=8192,
                    required_keys={"title"},
                )
        else:
            raise

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
