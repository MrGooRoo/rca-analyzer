"""
Сервис извлечения структурированных полей инцидента из текста отчёта через LLM.

Стратегия: параллельный вызов LLM для 4 групп полей через asyncio.gather.
Каждая группа — отдельный запрос с маленькой схемой и своим лимитом токенов.
Итоговый словарь собирается слиянием 4 ответов.

Группы:
  1. metadata     — title, date, time, company, location, severity, type (~500 tok)
  2. description  — description, short_description, scene_description, equipment_description (~4000 tok)
  3. narrative    — full_circumstances, established_facts, actions_taken (~8000 tok)
  4. victims      — victims_list (~4000 tok)

Timeout на каждую группу: 300 сек 
(допускает до 5 мин на генерацию длинных полей narrative).
"""

from __future__ import annotations

import asyncio
import logging

from src.integrations.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Контекстное окно модели
# ---------------------------------------------------------------------------

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
                "использую автоопределение", explicit,
            )
    model_id = getenv("OPENROUTER_MODEL", "").lower()
    for key, ctx in _KNOWN_MODEL_CONTEXTS.items():
        if key in model_id:
            return ctx
    return 131_072


def _model_supports_full_text(model_ctx_tokens: int) -> bool:
    return model_ctx_tokens >= _LARGE_CONTEXT_THRESHOLD_TOKENS


# ---------------------------------------------------------------------------
# Обрезка текста
# ---------------------------------------------------------------------------

_DEFAULT_MAX_INPUT_CHARS = 20_000
HEAD_CHUNK = 10_000
TAIL_CHUNK = 10_000
SECTION_WINDOW = 14_000


def _get_max_input_chars() -> int:
    from os import getenv
    val = getenv("DOCX_MAX_INPUT_CHARS")
    if val:
        try:
            return int(val)
        except ValueError:
            logger.warning("[DocxFields] Некорректный DOCX_MAX_INPUT_CHARS=%s", val)
    return _DEFAULT_MAX_INPUT_CHARS


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
    return "".join(parts), True


# ---------------------------------------------------------------------------
# Параллельное извлечение: 4 группы полей
# ---------------------------------------------------------------------------

# Timeout на каждую группу отдельно — больше чем дефолтный OPENROUTER_TIMEOUT (120с),
# так как narrative может генерировать 16K токенов до 5 мин.
_GROUP_TIMEOUT = 300

_BASE_SYSTEM = """\
Ты — специалист по анализу отчётов об инцидентах на производстве.
Прочитай текст отчёта и извлеки из него ТОЛЬКО запрошенные поля.
Ответ — СТРОГО JSON-объект, без markdown, без пояснений.
Если поле невозможно определить — используй null.
"""

_SYSTEM_METADATA = _BASE_SYSTEM + """\
Верни JSON со следующими полями:
{
  "title": "Краткий заголовок инцидента",
  "incident_date": "YYYY-MM-DD или null",
  "incident_time": "HH:MM или null",
  "company": "Название компании или null",
  "department": "Подразделение или null",
  "location": "Место происшествия",
  "injured_count": число или null,
  "fatalities_count": число или null,
  "incident_type": "injury|equipment|fire|spill|near_miss|process_upset|security|environmental",
  "severity": "critical|major|moderate|minor|near_miss"
}
"""

_SYSTEM_DESCRIPTION = _BASE_SYSTEM + """\
Верни JSON со следующими полями.
Для текстовых полей извлекай текст ДОСЛОВНО из отчёта, не сокращай:
{
  "description": "Подробное описание инцидента",
  "short_description": "Краткое описание (1-3 предложения)",
  "scene_description": "Описание места происшествия (дословно)",
  "equipment_description": "Характеристика оборудования/объекта (дословно)",
  "equipment": "Название оборудования или null",
  "conditions": "Условия труда/среды или null"
}
"""

_SYSTEM_NARRATIVE = _BASE_SYSTEM + """\
Верни JSON со следующими полями.
Для всех полей извлекай текст ДОСЛОВНО, сохраняя все абзацы, списки и пункты ПОЛНОСТЬЮ:
{
  "full_circumstances": "Полное описание обстоятельств происшествия (дословно)",
  "established_facts": "Установленные факты — весь список/хронология без потери пунктов (дословно)",
  "actions_taken": "Принятые меры или null"
}
"""

_SYSTEM_VICTIMS = _BASE_SYSTEM + """\
Верни JSON с одним полем:
{
  "victims_list": [
    {
      "full_name": "ФИО",
      "birth_date": "YYYY-MM-DD или null",
      "age": число или null,
      "family_status": "семейное положение или null",
      "children_under_21": число или 0,
      "profession": "профессия/должность",
      "workplace": "место работы",
      "total_experience": "общий стаж или null",
      "experience_in_organization": "стаж в организации или null",
      "qualification_certificate": "квалификационное удостоверение или null",
      "introductory_briefing": "вводный инструктаж или null",
      "workplace_briefing": "инструктаж на рабочем месте или null",
      "internship": "стажировка/допуск или null",
      "safety_knowledge_test": "проверка знаний или null",
      "medical_examination": "медосмотр или null",
      "diagnosis_severity": "диагноз / степень тяжести или null"
    }
  ]
}
Если пострадавших нет — верни {"victims_list": []}.
"""

_USER_PROMPT_TEMPLATE = """\
Проанализируй следующий текст отчёта об инциденте и извлеки запрошенные поля.

--- ТЕКСТ ОТЧЁТА ---
{report_text}
--- КОНЕЦ ОТЧЁТА ---
"""


async def _extract_group(
    group_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    required_keys: set[str],
) -> dict:
    """\u041e\u0434\u0438\u043d \u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u044b\u0439 \u0432\u044b\u0437\u043e\u0432 LLM \u0434\u043b\u044f \u0433\u0440\u0443\u043f\u043f\u044b \u043f\u043e\u043b\u0435\u0439."""
    logger.info("[DocxFields] \u0417\u0430\u043f\u0440\u043e\u0441 \u0433\u0440\u0443\u043f\u043f\u044b '%s' ...", group_name)
    try:
        async with OpenRouterClient(timeout=_GROUP_TIMEOUT) as client:
            result = await client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=max_tokens,
                required_keys=required_keys,
            )
        result.pop("_meta", None)
        logger.info("[DocxFields] \u0413\u0440\u0443\u043f\u043f\u0430 '%s' \u2014 \u0443\u0441\u043f\u0435\u0448\u043d\u043e (%d \u043a\u043b\u044e\u0447\u0435\u0439)", group_name, len(result))
        return result
    except Exception as exc:
        logger.error("[DocxFields] \u0413\u0440\u0443\u043f\u043f\u0430 '%s' \u2014 \u043e\u0448\u0438\u0431\u043a\u0430: %s", group_name, exc)
        return {}


async def extract_fields_from_text(report_text: str) -> dict:
    if not report_text or not report_text.strip():
        raise ValueError("\u0422\u0435\u043a\u0441\u0442 \u043e\u0442\u0447\u0451\u0442\u0430 \u043f\u0443\u0441\u0442\u043e\u0439 \u2014 \u043d\u0435\u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e \u0438\u0437\u0432\u043b\u0435\u0447\u044c \u0434\u0430\u043d\u043d\u044b\u0435.")

    model_ctx = _get_model_context_limit()
    full_text_ok = _model_supports_full_text(model_ctx)

    if full_text_ok:
        text_to_send = report_text
        logger.info(
            "[DocxFields] \u041c\u043e\u0434\u0435\u043b\u044c \u0441 \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043e\u043c %d \u0442\u043e\u043a\u0435\u043d\u043e\u0432 \u2014 "
            "\u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u044e \u043f\u043e\u043b\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 (%d \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432) \u0431\u0435\u0437 \u043e\u0431\u0440\u0435\u0437\u043a\u0438",
            model_ctx, len(report_text),
        )
    else:
        max_chars = _get_max_input_chars()
        text_to_send, was_trimmed = _trim_text(report_text, max_input_chars=max_chars)
        if was_trimmed:
            logger.warning(
                "[DocxFields] \u0422\u0435\u043a\u0441\u0442 \u043e\u0431\u0440\u0435\u0437\u0430\u043d (\u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 %d \u0442\u043e\u043a\u0435\u043d\u043e\u0432): %d \u2192 %d \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432",
                model_ctx, len(report_text), len(text_to_send),
            )

    user_prompt = _USER_PROMPT_TEMPLATE.format(report_text=text_to_send)

    results = await asyncio.gather(
        _extract_group(
            "metadata",
            _SYSTEM_METADATA,
            user_prompt,
            max_tokens=1024,
            required_keys={"title"},
        ),
        _extract_group(
            "description",
            _SYSTEM_DESCRIPTION,
            user_prompt,
            max_tokens=8192,
            required_keys={"description"},
        ),
        _extract_group(
            "narrative",
            _SYSTEM_NARRATIVE,
            user_prompt,
            max_tokens=16384,
            required_keys={"established_facts"},
        ),
        _extract_group(
            "victims",
            _SYSTEM_VICTIMS,
            user_prompt,
            max_tokens=8192,
            required_keys={"victims_list"},
        ),
        return_exceptions=True,
    )

    merged: dict = {}
    for group_result in results:
        if isinstance(group_result, Exception):
            logger.warning("[DocxFields] Группа упала в gather: %s", group_result)
            continue
        merged.update(group_result)  # type: ignore[arg-type]

    if not merged.get("title"):
        logger.error("[DocxFields] \u0413\u0440\u0443\u043f\u043f\u0430 'metadata' \u043d\u0435 \u0432\u0435\u0440\u043d\u0443\u043b\u0430 title \u2014 \u0432\u0441\u0435 \u0433\u0440\u0443\u043f\u043f\u044b \u0443\u043f\u0430\u043b\u0438?")
        raise ValueError("LLM \u043d\u0435 \u0441\u043c\u043e\u0433 \u0438\u0437\u0432\u043b\u0435\u0447\u044c \u0434\u0430\u043d\u043d\u044b\u0435 \u043d\u0438 \u0438\u0437 \u043e\u0434\u043d\u043e\u0439 \u0433\u0440\u0443\u043f\u043f\u044b \u043f\u043e\u043b\u0435\u0439.")

    fields = _normalize_fields(merged)

    logger.info(
        "[DocxFields] \u0418\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u044b \u043f\u043e\u043b\u044f: title=%s, victims=%d",
        fields.get("title", "")[:60],
        len(fields.get("victims_list") or []),
    )

    return fields


VALID_TYPES = {
    "injury", "equipment", "fire", "spill",
    "near_miss", "process_upset", "security", "environmental",
}
VALID_SEVERITIES = {"critical", "major", "moderate", "minor", "near_miss"}


def _normalize_fields(raw: dict) -> dict:
    fields: dict = {}
    fields["title"] = str(raw.get("title", "\u0418\u043d\u0446\u0438\u0434\u0435\u043d\u0442 (\u0438\u0437 \u043e\u0442\u0447\u0451\u0442\u0430)"))[:200]
    fields["description"] = str(raw.get("description", ""))
    fields["incident_date"] = str(raw.get("incident_date", "")) or None
    fields["incident_time"] = str(raw.get("incident_time", "")) or None
    fields["company"] = str(raw.get("company", "")) or None
    fields["department"] = str(raw.get("department", "")) or None
    fields["location"] = str(raw.get("location", ""))
    fields["injured_count"] = int(raw.get("injured_count") or 0) or None
    fields["fatalities_count"] = int(raw.get("fatalities_count") or 0) or None
    fields["short_description"] = str(raw.get("short_description", "")) or None
    it = str(raw.get("incident_type", "")).lower().strip()
    fields["incident_type"] = it if it in VALID_TYPES else "process_upset"
    sev = str(raw.get("severity", "")).lower().strip()
    fields["severity"] = sev if sev in VALID_SEVERITIES else "moderate"
    for key in (
        "equipment", "conditions", "actions_taken",
        "scene_description", "equipment_description",
        "full_circumstances", "established_facts",
    ):
        val = raw.get(key)
        fields[key] = str(val) if val and str(val).lower() != "null" else None
    victims_raw = raw.get("victims_list", [])
    fields["victims_list"] = victims_raw if isinstance(victims_raw, list) else []
    return fields
