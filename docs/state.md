# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении.

## Статус: 🟢 Рабочая версия — приоритет C завершён

**Дата обновления:** 2026-06-08

## Инфраструктура
- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI) + PostgreSQL
- LLM: `nvidia/nemotron-3-super-120b-a12b:free` (1M контекст)

## Готово
- [x] Все 5 методологий
- [x] Авторизация, CSRF, роли admin/user
- [x] Анализ, результаты, экспорт DOCX/PDF, upload DOCX
- [x] **Сравнение методик — бэкенд** (08.06.2026)
  - POST /api/v1/analyze-multi
  - GET /api/v1/results/compare?incident_id=...
  - Модели MultiAnalysisRequest + ComparisonResult
- [x] **Сравнение методик — UI** (08.06.2026, приоритет B)
  - Режим «Одна методика» / «Сравнить методики» в IncidentForm
  - CompareView: сводка, общие рекомендации, различающиеся выводы, side-by-side табы
- [x] **Приоритет C — Почистить/улучшить бэкенд** (08.06.2026)
  - ✅ Валидация MultiAnalysisRequest: мин 2, макс 5 уникальных методик (422 при нарушении)
  - ✅ Обработка ошибок в /analyze-multi (400, 502, 500) и /results/compare (404, 500)
  - ✅ Улучшен compare() — нечёткое сравнение через SequenceMatcher (порог 0.55)
  - ✅ Общие рекомендации (в ≥2 методиках), уникальные причины, информативная сводка
  - ✅ Фикс маршрутизации: /results/compare ДО /results/{result_id}
  - ✅ 24 новых теста (валидация, compare-логика, роуты /analyze-multi, /results/compare)
  - ✅ conftest.py с env vars для тестов
  - ✅ Обновлены contracts.md и state.md

## В работе / следующий приоритет
- [ ] **D — Векторный поиск похожих инцидентов (RAG)**

## Известные проблемы (предсуществующие)
- `test_analyze_router.py` — 6 тестов падают (401 Unauthorized) — нужен conftest с env + auth override
- `test_analysis_service.py::test_unsupported_methodology_raises` — устарел (bowtie теперь реализован)
- `test_methodologies_e2e.py` — 16 падений (интеграционные, зависит от LLM/шаблонов)
