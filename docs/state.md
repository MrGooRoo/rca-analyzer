# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении. Вставлять в новые AI-чаты как контекст.

## Статус: 🟢 Рабочая версия (v0.5.0)

**Дата обновления:** 2026-06-07

## Инфраструктура

- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI, :8000) + `rca-analyzer-db-1` (PostgreSQL)
- LLM: OpenRouter → `openai/gpt-4o-mini` (fallback: `gpt-oss-120b:free`)

## Готово

- [x] Все 5 методологий: `five_why`, `ishikawa`, `rca_systemic`, `fta`, `bowtie`
- [x] Авторизация: access JWT (15 мин) + refresh-token rotation в httpOnly cookie, bcrypt
- [x] CSRF: signed double-submit cookie (`X-CSRF-Token`)
- [x] `POST /api/v1/analyze`, `GET /api/v1/results[/{id}]`, экспорт DOCX
- [x] `POST /api/v1/upload-report` — DOCX → автозаполнение формы через LLM
- [x] Извлечение `established_facts` из длинных документов
      (head + tail + section-aware в `docx_fields_service._trim_text`, `max_tokens=4096`)
- [x] Unit-тесты `_trim_text` (`tests/unit/test_docx_fields_service.py`, 13 шт.)
- [x] Скрипт ручной проверки `scripts/verify_established_facts.py`

## В работе / следующий приоритет

- [ ] Роли `admin` / `user` (admin видит все результаты) — есть `tests/api/test_roles.py`, `test_admin.py`
- [ ] E2E-тесты `pytest` для всех 5 методологий
- [ ] PDF-экспорт (дополнительно к DOCX)

## Заметки

- В чистом sandbox без `respx` / `pytest-asyncio` часть валидационных тестов
  (`test_openrouter*`, `test_rca_systemic`, `test_analysis_service`) падает на
  collection/версиях библиотек — это окружение, не код. В проектном окружении
  (`pip install -e .`) запускать как обычно.
