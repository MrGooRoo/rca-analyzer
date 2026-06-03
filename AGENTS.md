# AGENTS.md — Инструкции для AI-ассистента

> Этот файл нужно передавать в начале каждого нового чата вместе с `docs/contracts.md`.

## Что это за проект

Веб-приложение для анализа корневых причин производственных инцидентов (RCA).
На входе — параметры происшествия, на выходе — структурированный анализ с корневыми причинами и рекомендациями.

## Стек

- Python 3.12, FastAPI, Pydantic v2
- PostgreSQL + pgvector
- OpenRouter API (LLM)
- React + D3.js / React Flow (frontend)

## Правила

1. **Читай `docs/contracts.md` перед любыми изменениями** — там все типы данных
2. **Не изобретай свои структуры данных** — используй модели из contracts.md
3. **Новая методика** → новый файл в `src/domain/methodologies/`, наследует `base.py`
4. **Промпты** хранятся в `configs/prompts/*.j2`, не в коде
5. **После изменений** обновляй `docs/state.md`
6. **Тесты** для новых модулей — обязательно в `tests/`

## Структура проекта

```
rca-analyzer/
├── AGENTS.md          ← этот файл
├── docs/
│   ├── contracts.md   ← ГЛАВНЫЙ файл, читать первым
│   ├── architecture.md
│   ├── conventions.md
│   ├── methodologies.md
│   └── state.md       ← текущий статус проекта
├── configs/
│   ├── app.yaml
│   ├── models.yaml
│   └── prompts/       ← Jinja2 шаблоны промптов
├── src/
│   ├── api/
│   ├── domain/
│   │   └── methodologies/
│   ├── services/
│   ├── integrations/
│   │   ├── llm/
│   │   ├── db/
│   │   └── export/
│   └── utils/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contracts/     ← тесты на стыки модулей
├── frontend/
├── scripts/
└── notebooks/
```

## Как запускать

```bash
# TODO: заполнить после настройки окружения
```
