# state.md — Текущее состояние проекта

> Обновлять при каждом значимом изменении. Вставлять в новые AI-чаты как контекст.

## Статус: 🟢 Рабочая версия — целевой функционал реализован

**Дата обновления:** 2026-06-07 (контракты синхронизированы)

## Инфраструктура

- Репозиторий: `MrGooRoo/rca-analyzer`
- Docker Compose: `rca-analyzer-api-1` (FastAPI, :8000) + `rca-analyzer-db-1` (PostgreSQL)
- LLM: OpenRouter → `nvidia/nemotron-3-super-120b-a12b:free` (1M контекст; fallback-цепочка в scripts/ и openrouter.py)

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
- [x] Роли `admin` / `user` — admin видит/редактирует/удаляет любые результаты,
      user только свои (`analyze._check_owner_or_admin`, `auth.service.require_admin`,
      admin-роутер `/api/v1/admin/users`, миграция `005_add_user_role`,
      seed по `ADMIN_EMAIL`); тесты `tests/api/test_roles.py` (10) + `test_admin.py` (8)
- [x] E2E-тесты всех 5 методологий через полный конвейер сервиса
      (`tests/integration/test_methodologies_e2e.py`, 21 тест) — реальные промпты
      и runner'ы, мокается только сетевой вызов LLM
- [x] PDF-экспорт (`pdf_export_service.generate_pdf`, fpdf2 + встроенные
      DejaVu-шрифты для кириллицы); эндпоинт `GET …/export?format=pdf`;
      в UI кнопка ⬇️ PDF (`api.exportResult`, `ResultView.jsx`);
      тесты `tests/unit/test_pdf_export_service.py` (8)

## В работе / следующий приоритет

- Активных задач нет — основной целевой функционал реализован.
- Backlog «Идеи на будущее» см. в `README.md` → Roadmap (доп. форматы экспорта,
  дашборд статистики, сравнение методик и т.д.).
- Мультиязычный интерфейс (EN/RU) решено **не** делать.

## Известные несоответствия (вне текущих задач)

(Все основные несоответствия устранены обновлением `docs/contracts.md` под актуальные `src/domain/models.py` и `docx_fields_service` / промпты. Тесты `test_models.py` и `test_rca_systemic.py` теперь согласованы с кодом: `IncidentType` удалён из импортов/контрактов, barriers — опциональны в rca_systemic.)

- Остаточные проблемы только из-за окружения sandbox (отсутствующие пакеты типа tenacity при запуске pytest напрямую).

## Заметки про окружение

- В чистом sandbox (новые версии pydantic/httpx/respx, без реальной БД) часть
  валидационных тестов (`test_openrouter*`, `test_analyze_router`,
  `test_analysis_service`) падает из-за версий библиотек — это окружение, не код.
  В проектном Docker/`pip install -e .` запускать как обычно.
