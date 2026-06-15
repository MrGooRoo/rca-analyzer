# 🧊 Капсула памяти — RCA Analyzer

> Дата: 2026-06-15 (03:47 MSK)
> Назначение: передать этот файл в начало нового чата для бесшовного продолжения разработки RCA Analyzer.

---

## 1. Репозиторий и среда

**Репозиторий:** `MrGooRoo/rca-analyzer`

### Среда пользователя
- Windows 10, Docker Desktop
- Локальный путь проекта: `C:\Users\Mr_GooRoo\rca-analyzer`
- Docker data перенесён на `D:\DockerData`
- Локальный Python 3.14 хрупкий — backend/pytest/ruff лучше гонять через Docker
- Frontend-команды выполняются локально через `npm`
- Пользователь не разработчик: команды давать простыми пошаговыми `cmd`-командами
- Пользователь просит экономить запросы Agent Mode: если можно решить одним ответом, давать сразу полный блок команд

Если `git pull` зависает на `Unlink ... failed. Should I try again? (y/n)` — ответить `n`, затем `git status`.

### Адреса
| Что       | Адрес                          |
|-----------|-------------------------------|
| Frontend  | http://localhost:5173/         |
| API docs  | http://localhost:8000/docs     |
| Health    | http://localhost:8000/health   |

---

## 2. Актуальный HEAD на момент создания капсулы

```text
20ca528 feat(frontend): add neutral incident form placeholders
70580af feat(frontend): add input method selector
29e80e9 feat(frontend): clarify docx and manual fill flow
af74247 Revert "feat(frontend): improve analysis form quick wins"
```

> Важно: `22657f3 improve analysis form quick wins` был крупным Batch A,
> откат `af74247`. После этого — **строго по одному пункту**.

---

## 3. Договорённости по формату работы

### 3.1. Формат ответа
1. Коротко сказать, что исправляется
2. Какие файлы изменены
3. Что реализовано
4. Проверки
5. Patch-файл для скачивания
6. **Одна** конкретная команда для apply → check → commit → push
7. В конце: `Модель ИИ, выполнившая задачу: конкретная внутренняя модель не раскрывается платформой.`

### 3.2. Нумерация patch-файлов
Формат: `NN-short-description.patch`  
Перед новым patch-файлом удалять старые: `find /home/user -maxdepth 1 -name '*.patch' -type f -print -delete`

### 3.3. Не делать крупные batch-патчи без согласования
Внедрять доработки **по одному пункту**. Не трогать несвязанные компоненты.

### 3.4. Agent Mode quota
Агент не видит остаток квоты — честно сообщать об этом.

---

## 4. Обязательные файлы к чтению в новом чате

```text
AGENTS.md
docs/contracts.md
docs/state.md
docs/user-feedback-backlog.md
```

Актуальный HEAD:
```bash
git ls-remote https://github.com/MrGooRoo/rca-analyzer.git refs/heads/main
git log --oneline -12 origin/main
```

---

## 5. Запуск проекта

### Backend + DB
```cmd
cd C:\Users\Mr_GooRoo\rca-analyzer
docker compose up -d --build
docker compose exec api alembic upgrade head
```

### Frontend
```cmd
cd C:\Users\Mr_GooRoo\rca-analyzer\frontend
npm run dev -- --host 0.0.0.0
```

---

## 6. Стандартные проверки перед commit/push

```cmd
docker compose exec api ruff check
docker compose exec api python -m pytest tests/ -q
npm --prefix frontend run build
```

---

## 7. Статус всех задач

### ✅ Полностью завершено и запушено

| # | Задача | Коммит |
|---|--------|--------|
| — | P3 — предупреждение при уходе во время анализа | `App.jsx` |
| — | P4 — отмена анализа через AbortController | `2c60bae` |
| — | Техдолг CSRF/httpx warnings | `3068353` |
| — | Документация architecture/conventions/methodologies | `bccf1bd` |
| — | Feedback #1 — логика ручного ввода и DOCX-дозаполнения | — |
| — | Feedback #1.1 — явный выбор способа ввода | `70580af` |
| — | Feedback #2/#3 — нейтральные плейсхолдеры | `20ca528` |
| — | UI-kit + Tailwind + Toast + AuthContext | — |
| — | App.jsx мигрирован на UI-kit | — |
| — | IncidentForm.jsx на UI-kit | — |
| — | HistoryPage.jsx на UI-kit | — |
| — | SimilarIncidentsPanel.jsx на UI-kit | — |
| — | Сущность analysis_session в БД | — |
| — | Docker-интеграция HF-эмбеддингов | — |
| — | UX похожих инцидентов | — |
| — | incident_hash + фильтр повторных анализов | — |
| — | Контекст инцидента в карточках похожих | — |
| — | Блокировка формы при анализе/загрузке DOCX | — |
| — | Индикатор похожих в форме, полный блок в результате | — |
| — | AnalysisProgress SSE-прогресс multi-analysis | — |
| — | P2/P6 — явные UI-состояния анализа | — |
| — | История: сравнение = одно исследование | — |

### 🔴 В работе — Feedback #4/#6: пошаговый ввод (степпер/wizard)

#### Что было сделано (простой патч, без wizard)

Сделан визуальный степпер `AnalysisSteps.jsx` — **декоративный**, без разделения формы на экраны:

- Компонент `AnalysisSteps` с 3 шагами: «Исходные данные» / «Методология» / «Результат»
- `analysisStep` в `App.jsx` вычисляется как `comparison || result ? 3 : loading ? 2 : 1`
- `onNavigate` **не передан** в `App.jsx` → кнопки шагов не кликабельны
- Якоря `id="step-data"`, `id="step-method"`, `id="step-result"` расставлены в форме

#### Выявленные проблемы с текущей реализацией

1. **Степпер декоративный** — не управляет показом/скрытием блоков формы
2. **Шаг 1 и 2 визуально не различаются** — форма всегда показывает все поля сразу
3. **Шаг 2 («Методология») активен только во время загрузки** — пользователь его не «видит» в покое
4. **Кнопки степпера не кликабельны** — `onNavigate` не передан из `App.jsx`
5. **Прогресс-линия между шагами** работает странно

#### Решение, обсуждённое с пользователем

Пользователь согласился сделать **полноценный wizard (Вариант B)**:

- **Шаг 1**: только поля данных инцидента → кнопка «Далее»
- **Шаг 2**: выбор методологии → кнопка «Анализировать»
- **Шаг 3**: результат
- Форма физически разделяется на экраны, степпер управляет показом

**Следующий патч**: `05-wizard-steps.patch`  
Затронутые файлы: `frontend/src/components/IncidentForm.jsx`, `frontend/src/App.jsx`, `frontend/src/components/AnalysisSteps.jsx`

---

## 8. Известные проблемы / нюансы

- `EMBEDDINGS_PROVIDER=huggingface`: первый запрос скачивает модель (~120MB) — нужен volume под `HF_HOME`
- Дефолтный `threshold=0.15` слишком низкий для HF — рекомендуется 0.55–0.6
- Смешивать провайдеры безопасно: поиск фильтрует по `model_name`
- После смены провайдера старые векторы переиндексируются лениво (батчами по 100)
- На существующей БД после обновления: `alembic upgrade head`

---

## 9. Тесты на момент создания капсулы

```text
257 passed, 1 deselected (slow)
ruff check → All checks passed!
npm run build → успешно
```
