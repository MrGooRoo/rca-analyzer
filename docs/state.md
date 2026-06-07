# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟢 Рабочая версия — целевой функционал реализован

**Дата обновления:** 2026-06-08

## Инфраструктура
- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI) + PostgreSQL
- LLM: `nvidia/nemotron-3-super-120b-a12b:free` (1M контекст)

## Готово
- [x] Все 5 методологий
- [x] Авторизация, CSRF, роли admin/user
- [x] Анализ, результаты, экспорт DOCX/PDF, upload DOCX
- [x] **Сравнение методик** (добавлено 08.06.2026)
  - POST /api/v1/analyze-multi
  - GET /api/v1/results/compare?incident_id=...
  - Модели MultiAnalysisRequest + ComparisonResult
  - Автоматическая сводка общих рекомендаций и расхождений

## В работе / следующий приоритет
- Векторный поиск похожих инцидентов