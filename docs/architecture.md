# architecture.md — Архитектура RCA Analyzer

> TODO: описать схему модулей, слои и зависимости между ними.

## Слои приложения

```
frontend/ (React)
    ↓ HTTP REST
src/api/           ← FastAPI роутеры
    ↓
src/services/      ← Оркестрация сценариев
    ↓           ↘
src/domain/    src/integrations/
  methodologies/   llm/ (OpenRouter)
  models.py        db/  (PostgreSQL + pgvector)
  scoring.py       export/ (PDF, Excel)
```

## Модули

| Модуль | Ответственность |
|--------|----------------|
| `api/` | HTTP-слой, валидация запросов, маршрутизация |
| `services/` | Сценарии использования, оркестрация |
| `domain/` | Бизнес-логика, независима от фреймворков |
| `integrations/` | Внешний мир: LLM, БД, экспорт |
| `utils/` | Логирование, общие утилиты |
