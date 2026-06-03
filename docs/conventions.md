# conventions.md — Соглашения проекта

> TODO: заполнить по мере принятия решений.

## Стек

- **Backend:** Python 3.12, FastAPI, Pydantic v2
- **LLM:** OpenRouter API (бюджет ~$10/день на MVP)
- **БД:** PostgreSQL + pgvector
- **Frontend:** React + D3.js / React Flow
- **Экспорт:** WeasyPrint (PDF), openpyxl (Excel)
- **Auth:** JWT, RBAC

## Нейминг

- Файлы и модули: `snake_case`
- Классы: `PascalCase`
- Константы: `UPPER_SNAKE_CASE`
- API-эндпоинты: `/api/v1/resource_name`

## Язык

- Комментарии в коде: русский
- Имена переменных и функций: английский
- Документация (docs/): русский
