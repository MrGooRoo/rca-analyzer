# User Feedback Backlog

> Последнее обновление: 2026-06-17 MSK
> HEAD: после docs-only фиксации п.17; п.17 следующий к реализации

---

## Таблица фидбэков

| # | Описание | Статус | Коммит / документ |
|---|----------|--------|-------------------|
| 1 | Логика ручного ввода и DOCX-дозаполнения | ✅ done | текущий |
| 1.1 | Явный выбор способа ввода данных | ✅ done | текущий |
| 2 | Убрать placeholder-примеры с реальными кейсами | ✅ done | текущий |
| 3 | Нейтральные placeholder-подсказки | ✅ done | текущий |
| 4 | Поэтапный ввод данных | 🔜 | — |
| 5 | Прогресс анализа через SSE (multi) | ✅ done | `9df52a9` |
| 6 | Переключатель параметров анализа | 🔜 | — |
| 7 | Группировка истории по исследованиям | ✅ done | текущий |
| 8 | Сохранение черновика формы при переходе в Историю | ✅ done | `26df63c` |
| 9 | Похожие инциденты в форме (индикатор) | ✅ done | текущий |
| 10 | Единый формат названий методик | ✅ done | `76a7dd1` |
| 11 | Порядок методик и default: 5 Почему первым | ✅ done | `26df63c` |
| 12 | Сохранение черновика формы при переходе Анализ → История | ✅ done | текущий |
| 13 | Кнопка «Отменить анализ» — аккуратное оформление | ✅ done | `22580d5` |
| 14 | Шкала / процент обработки анализа | ✅ done | `8ad9b87` |
| 15 | Статус выполнения для одиночного анализа | ✅ done | `9200b00` |
| 16 | Оптимизация скорости обработки | ✅ done | `a686cf6`, `798c172`, `d00e251`, cleanup `72e84b2` |
| **17** | **LLM Conductor: бесплатный черновик + дешёвый verifier по порогу качества** | 🟡 **in progress** | этап 1: DB/API settings |
| 18 | Упростить страницу результата (убрать «Форма скрыта…», меньше вложенности) | 🔜 | — |
| 19 | Кнопка «Открыть» в похожих инцидентах — логика и куда ведёт | 🔜 | — |

---

## Детали по закрытым пунктам

### Feedback #15 — SSE-статус для одиночного анализа (16.06.2026)
- Backend: `POST /api/v1/analyze-stream` — SSE-стрим одиночного анализа.
- Frontend: `SingleAnalysisProgress` + `api.analyzeStream()`.
- Итоговая проверка: **268 passed, 1 deselected**.

### Feedback #16 — оптимизация скорости обработки (16.06.2026)
- `OpenRouterClient` использует общий `httpx.AsyncClient` в процессе: keep-alive / connection reuse.
- Жизненный цикл защищён `asyncio.Lock` и счётчиком ссылок.
- FastAPI shutdown вызывает `OpenRouterClient.close_shared()`.
- Временный `p16-only.patch` удалён из репозитория.
- Финальная проверка после cleanup: **269 passed, 1 deselected**, targeted `ruff check` — **All checks passed!**

---

## Следующий пункт

### Feedback #17 — LLM Conductor (архитектура зафиксирована 17.06.2026)

Уточнение пользователя: задача не в простом fallback/«подмешивании» моделей. Нужна схема дирижирования:

```text
бесплатная/дешёвая draft_model → черновой RCAResult
confidence_avg < quality_threshold?
    да  → дешёвая verifier_model проверяет и улучшает JSON-черновик
    нет → черновик становится финальным результатом
```

Зафиксированные решения:

- Модели не хардкодятся в Python: admin настраивает `draft_model` и `verifier_model` в кабинете.
- Основной режим — `verification_scheme="threshold"` по `confidence_avg`; default threshold `0.70`.
- Дополнительные схемы: `disabled` и `always`.
- Настройки хранить в отдельной singleton-таблице `llm_settings`, а не в произвольном JSON.
- OpenRouter catalog желательно получать программно через backend proxy к `GET https://openrouter.ai/api/v1/models` и показывать select/autocomplete; ручной ввод slug остаётся fallback.
- Дешёвые verifier-кандидаты: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, их `:free` варианты, `openai/gpt-4o-mini`, `google/gemini-2.5-flash-lite`.
- Верификатор выполняет лёгкую проверку/улучшение черновика, не полный повторный анализ.
- Подробный план: [`docs/p17-llm-conductor-plan.md`](p17-llm-conductor-plan.md).

Порядок реализации P17:

1. ✅ DB/API settings: migration `011_add_llm_settings.py`, ORM, Pydantic, upsert, admin-only `GET/PUT /llm-settings`.
2. 🔜 OpenRouter catalog proxy: `GET /api/v1/admin/openrouter/models` + кэш и тесты.
3. Admin UI: блок LLM-настроек с select/autocomplete и ручным fallback.
4. `configs/prompts/verifier.j2`.
5. `LLMConductor` и интеграция в `AnalysisService.analyze()` / `analyze_stream()`.
6. Аудит token/model provenance.

---

## Заметки

- Пункты 1–16 закрыты. **П.17 в работе**: этап 1 DB/API settings реализован, следующий этап — OpenRouter catalog proxy.
- П.5 потребовал 3 итерации (9df52a9 → de0cd5b → 3c1e6d7).
- П.8 был уже реализован в `26df63c` (обнаружено при аудите).
- Не делать крупные batch-патчи: строго один пункт за раз.
