# P17 — LLM Conductor: черновая бесплатная модель + дешёвый верификатор

> Статус: 🟡 **архитектура зафиксирована, код ещё не менять**
> Дата фиксации: 2026-06-17 MSK
> Основание: уточнение пользователя — задача не в простом fallback/«подмешивании», а в дирижировании моделей: максимум токенов тратится на бесплатную черновую модель, платная/дешёвая модель подключается только для чистовой верификации при недостаточной уверенности.

---

## 1. Цель

Реализовать управляемую администратором схему работы LLM:

```text
IncidentInput + methodology
        │
        ▼
1) draft_model — черновой RCA-анализ
   желательно бесплатная OpenRouter-модель
        │
        ▼
2) quality gate по confidence_avg
        │
        ├─ confidence_avg >= threshold → черновик становится финальным результатом
        │
        └─ confidence_avg < threshold  → verifier_model получает черновик и улучшает/проверяет его
```

Ключевая идея: **платная модель не делает полный анализ заново**. Она получает входной инцидент, методологию и JSON-черновик, после чего исправляет слабые места, нормализует структуру, повышает связность рекомендаций и возвращает тот же контракт `RCAResult`/LLM JSON. Так платные токены уходят только на чистовую отделку.

---

## 2. Решение по хранению настроек

В текущей структуре репозитория нет универсальной таблицы `system_config`; есть явные ORM-таблицы в `src/db/orm_models.py` и Alembic-миграции `001`–`010`.

### Рекомендуемый вариант: отдельная singleton-таблица `llm_settings`

С точки зрения разработчика и безопасности это лучше, чем JSON в произвольном конфиге:

- **Типобезопасность:** отдельные поля для модели, порога и схемы вместо невалидируемого JSON.
- **DB-валидация:** `quality_threshold` можно ограничить `0.0..1.0`, `verification_scheme` — фиксированным enum/`CHECK`.
- **Аудит:** `updated_at`, `updated_by` показывают, кто менял LLM-настройки.
- **Меньше риска ошибок:** нельзя случайно сохранить произвольный ключ/структуру, которую код не ожидает.
- **Admin-only поверхность:** настройки меняются только через `/api/v1/admin/...` с уже существующей ролью `admin`.

Таблица хранит одну строку (`id=1`), при сохранении используется upsert.

```python
class LLMSettingsORM(Base):
    __tablename__ = "llm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    draft_model: Mapped[str] = mapped_column(String(200), nullable=False)
    verifier_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quality_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    verification_scheme: Mapped[str] = mapped_column(String(20), nullable=False, default="threshold")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

### Валидация

- `draft_model`: обязательная строка OpenRouter model id, например `nvidia/nemotron-3-super-120b-a12b:free`.
- `verifier_model`: nullable; если пусто, верификация фактически невозможна и должна быть отключена/проигнорирована.
- `quality_threshold`: `0.0 <= value <= 1.0`, default `0.70`.
- `verification_scheme`: одно из `disabled | threshold | always`.
- model id: trim, max length 200, без пробелов и управляющих символов. Практичный allowlist для slug: `A-Za-z0-9._~:/-`.

---

## 3. Схемы взаимодействия

| Схема | Когда вызывается verifier_model | Назначение |
|---|---|---|
| `disabled` | Никогда | Только черновая модель; самый дешёвый режим |
| `threshold` | Только если `draft_result.confidence_avg < quality_threshold` | Основной режим P17: экономия платных токенов |
| `always` | Всегда после черновика | Максимальное качество/контроль, но дороже |

Default для MVP: `verification_scheme="threshold"`, `quality_threshold=0.70`.

---

## 4. OpenRouter models: выбор из каталога + fallback на ручной ввод

Желательное поведение для админ-кабинета:

1. Backend добавляет admin-only proxy endpoint:

```text
GET /api/v1/admin/openrouter/models?search=&free_only=&limit=100
```

2. Endpoint сервер-сервером вызывает публичный каталог OpenRouter:

```text
GET https://openrouter.ai/api/v1/models
```

3. Frontend показывает searchable select/autocomplete:
   - `id` модели;
   - человекочитаемое имя;
   - context length;
   - prompt/completion price за 1M токенов;
   - признак `:free` или нулевая цена.

4. Если каталог недоступен, UI сохраняет возможность ручного ввода slug, чтобы пользователь мог скопировать model id из OpenRouter.

Безопасность:

- API key OpenRouter не отдаётся в браузер.
- Frontend не ходит напрямую в OpenRouter — только через backend proxy.
- Каталог можно кэшировать in-memory на 6–24 часа, чтобы не дергать внешний API при каждом открытии админки.
- Сохранение настроек всё равно валидирует model id, даже если он выбран из списка.

---

## 5. Дешёвые кандидаты на verifier_model

Цены OpenRouter меняются, поэтому их нельзя хардкодить в логике — показывать live из каталога. На момент фиксации архитектуры (2026-06-17) полезные кандидаты:

| Model id | Роль | Комментарий |
|---|---|---|
| `openai/gpt-oss-20b` | дешёвый verifier | Очень дешёвый платный вариант; подходит для лёгкой проверки/нормализации черновика |
| `openai/gpt-oss-120b` | более сильный дешёвый verifier | Дороже 20b, но всё ещё значительно дешевле классических GPT-4o/Claude |
| `openai/gpt-oss-20b:free` | бесплатный verifier при лимитах | Можно тестировать без расходов, но возможны rate limit/доступность |
| `openai/gpt-oss-120b:free` | бесплатный сильный verifier при лимитах | Хороший экспериментальный вариант, если лимиты позволяют |
| `openai/gpt-4o-mini` | запасной качественный verifier | Дороже gpt-oss, но стабильный недорогой baseline |
| `google/gemini-2.5-flash-lite` | дешёвый verifier | Альтернатива, если доступна и качество устраивает |

Важно: админ должен иметь возможность выбрать любую актуальную модель из OpenRouter, а не только этот список.

---

## 6. Backend-архитектура

### 6.1. Новые сущности

- Alembic migration `011_add_llm_settings.py`.
- ORM: `LLMSettingsORM` в `src/db/orm_models.py`.
- Pydantic-схемы в доменном/админском слое:

```python
class LLMSettings(BaseModel):
    draft_model: str
    verifier_model: str | None = None
    quality_threshold: float = Field(0.70, ge=0.0, le=1.0)
    verification_scheme: Literal["disabled", "threshold", "always"] = "threshold"
    updated_at: datetime | None = None
    updated_by: str | None = None

class LLMSettingsUpdate(BaseModel):
    draft_model: str
    verifier_model: str | None = None
    quality_threshold: float = Field(0.70, ge=0.0, le=1.0)
    verification_scheme: Literal["disabled", "threshold", "always"] = "threshold"
```

### 6.2. Admin API

```text
GET /api/v1/admin/llm-settings
PUT /api/v1/admin/llm-settings
GET /api/v1/admin/openrouter/models
```

Все endpoints:

- требуют `require_admin(current_user)`;
- используют существующие auth/cookie/CSRF механизмы;
- не раскрывают `OPENROUTER_API_KEY`;
- логируют изменение настроек без секрета.

### 6.3. Новый сервис `LLMConductor`

Файл: `src/services/llm_conductor.py`.

Ответственность:

1. Получить актуальные `LLMSettings`.
2. Выполнить draft-прогон через `OpenRouterClient(model=settings.draft_model, ...)`.
3. Преобразовать draft raw dict в `RCAResult` через существующий `MethodologyRunner`.
4. Решить, нужна ли верификация:

```python
should_verify = (
    settings.verification_scheme == "always"
    or (
        settings.verification_scheme == "threshold"
        and draft_result.confidence_avg < settings.quality_threshold
    )
)
```

5. Если верификация не нужна — вернуть draft_result.
6. Если нужна — вызвать `verifier_model` с новым prompt `configs/prompts/verifier.j2`, передав:
   - входной инцидент;
   - методологию;
   - draft JSON;
   - список причин/рекомендаций с низкой уверенностью;
   - требование вернуть тот же JSON-контракт.
7. Прогнать результат верификатора через тот же runner/parser, сохранить итог.

### 6.4. Интеграция с `AnalysisService`

`AnalysisService.analyze()` и `AnalysisService.analyze_stream()` должны использовать один и тот же conductor-путь, чтобы single HTTP и SSE давали одинаковую бизнес-логику.

SSE-стадии можно расширить без ломки существующего UI:

```text
started → preparing → llm_draft → parsing → verification? → done/error
```

Для обратной совместимости допускается сначала маппить `llm_draft` в существующий `llm`, а `verification` показывать отдельным сообщением внутри stage.

---

## 7. Контракт prompt verifier

Новый файл: `configs/prompts/verifier.j2`.

Принципы:

- Верификатор **не должен делать независимый анализ с нуля**, если это не нужно.
- Он должен проверять логичность причинно-следственных связей, полноту рекомендаций и формат.
- Он должен возвращать JSON того же формата, что и methodology prompt, чтобы существующие runners продолжили работать.
- Если черновик уже достаточный, верификатор может минимально исправить формулировки.
- Запрещено удалять важные причины без объяснимой замены.

Входные переменные:

```jinja2
{{ incident }}
{{ methodology }}
{{ draft_result_json }}
{{ low_confidence_nodes }}
{{ output_schema_hint }}
```

---

## 8. Аудит и метрики токенов

Чтобы контролировать экономику P17, финальный результат должен показывать, какие модели участвовали.

Минимальный совместимый вариант без немедленной миграции `rca_results`:

- `model_used`: `draft_model` если верификации не было;
- `model_used`: `draft_model -> verifier_model` если верификация была;
- `tokens_used`: сумма draft + verifier.

Рекомендуемый вариант для отдельного этапа P17/P17.1:

- `draft_model_used`
- `verifier_model_used`
- `draft_tokens_used`
- `verifier_tokens_used`
- `verification_applied`
- `verification_reason`

Так будет видно, сколько токенов ушло на бесплатный черновик и сколько — на платную чистовую отделку.

---

## 9. Frontend: админ-кабинет

`frontend/src/components/AdminPage.jsx` сейчас управляет пользователями. В P17 добавить отдельный блок/таб «LLM-настройки»:

- «Черновая модель» — autocomplete/select из `/admin/openrouter/models`, fallback ручной `Input`.
- «Верификатор» — autocomplete/select, можно оставить пустым.
- «Порог качества» — slider/number `0.00..1.00`, default `0.70`.
- «Схема верификации» — radio/select:
  - `disabled` — только черновик;
  - `threshold` — верификация ниже порога;
  - `always` — всегда верифицировать.
- Подсказка с ориентировочной ценой выбранной модели из каталога OpenRouter.
- Кнопка «Сохранить» → `PUT /api/v1/admin/llm-settings`.

UX-правила:

- Если `verification_scheme != disabled`, но `verifier_model` пустой — показать ошибку валидации.
- Если модель выбрана из каталога, сохранять именно `id`, не display name.
- Если каталог не загрузился — разрешить ручной ввод и показать предупреждение.

---

## 10. Порядок реализации

Строго один пункт за раз, без крупных batch-патчей.

1. ✅ **Docs-only фиксация P17** — этот документ + ссылки из `state.md`, `contracts.md`, `user-feedback-backlog.md`.
2. ✅ **DB/API settings:** migration `011`, ORM, Pydantic, repository/upsert, `GET/PUT /admin/llm-settings`, тесты.
3. ✅ **OpenRouter catalog:** backend proxy `/admin/openrouter/models`, кэш, тесты с моками.
4. ✅ **Admin UI:** блок LLM-настроек, загрузка/сохранение, валидация, ручной fallback.
5. **Verifier prompt:** `configs/prompts/verifier.j2` + unit tests prompt/render.
6. **LLMConductor:** draft → threshold gate → verifier → итоговый `RCAResult`; unit tests без реальных LLM.
7. **Integration:** `AnalysisService.analyze()` и `analyze_stream()` используют conductor; API/SSE tests.
8. **Observability:** token/model provenance в результате; при необходимости отдельная миграция.
9. **Final checks:** `python -m pytest tests/ -q`, `ruff check`, `cd frontend && npm run build && cd ..`.

---

## 11. Решения, которые считаются зафиксированными

- P17 = **дирижирование моделей**, не простой fallback.
- Черновую и verifier-модель выбирает admin, не хардкод в Python.
- Основной режим — verification by threshold через `confidence_avg`.
- Настройки лучше хранить в отдельной singleton-таблице `llm_settings`.
- OpenRouter catalog желательно получать программно через backend proxy; ручной ввод остаётся как fallback.
- Верификатор должен быть дешёвым и выполнять лёгкую проверку/улучшение черновика, а не полный повторный анализ.

---

## 12. Реализовано

### 12.1. Этап 1 — DB/API settings (17.06.2026)

Добавлено:

- `alembic/versions/011_add_llm_settings.py` — singleton-таблица `llm_settings` с seed `id=1`.
- `LLMSettingsORM` в `src/db/orm_models.py`.
- Pydantic-схемы `LLMSettingsUpdate`, `LLMSettings`, `OpenRouterModelInfo` в `src/domain/models.py`.
- `src/db/llm_settings_repository.py` — get-or-create и upsert singleton-настроек.
- Admin-only endpoints:
  - `GET /api/v1/admin/llm-settings`;
  - `PUT /api/v1/admin/llm-settings`.
- `tests/api/test_admin_llm_settings.py` — 5 API-тестов.

Проверки:

```text
pytest tests/api/test_admin.py tests/api/test_admin_llm_settings.py -q → 13 passed
python -m pytest tests/ -q → 274 passed, 1 deselected
ruff check src/domain/models.py src/db/orm_models.py src/db/llm_settings_repository.py src/api/routes/admin.py tests/api/test_admin_llm_settings.py → All checks passed!
```


### 12.2. Этап 2 — OpenRouter catalog proxy (17.06.2026)

Добавлено:

- `src/integrations/llm/openrouter_catalog.py` — server-side клиент публичного каталога OpenRouter.
- In-memory cache каталога с TTL `OPENROUTER_MODELS_CACHE_TTL_SECONDS` (default 6 часов).
- Admin-only endpoint `GET /api/v1/admin/openrouter/models` с параметрами:
  - `search`;
  - `free_only`;
  - `limit` (`1..500`);
  - `force_refresh`.
- Ответ — `OpenRouterModelInfo[]`: `id`, `name`, `context_length`, цены prompt/completion за 1M токенов, `is_free`.
- `tests/api/test_admin_openrouter_models.py` — 4 теста: права доступа, параметры, 502 при ошибке каталога, парсинг/фильтрация цен и free-флага.

Проверки:

```text
pytest tests/api/test_admin.py tests/api/test_admin_llm_settings.py tests/api/test_admin_openrouter_models.py -q → 17 passed
python -m pytest tests/ -q → 278 passed, 1 deselected
ruff check src/integrations/llm/openrouter_catalog.py src/api/routes/admin.py tests/api/test_admin_openrouter_models.py → All checks passed!
```


### 12.3. Этап 3 — Admin UI для LLM-настроек (17.06.2026)

Добавлено:

- `frontend/src/api.js`:
  - `api.admin.getLlmSettings()`;
  - `api.admin.updateLlmSettings(payload)`;
  - `api.admin.openRouterModels(params)`.
- `frontend/src/components/AdminPage.jsx`:
  - блок «LLM Conductor» над управлением пользователями;
  - загрузка/сохранение `draft_model`, `verifier_model`, `quality_threshold`, `verification_scheme`;
  - поиск моделей OpenRouter через backend proxy;
  - `datalist` для выбора model id + ручной fallback;
  - фильтр «Только бесплатные» и принудительное обновление каталога;
  - UX-подсказки по цене, схеме и экономике токенов.
- `frontend/src/components/AdminPage.css` — стили блока настроек.

Проверки:

```text
cd frontend && npm run build → built successfully
python -m pytest tests/ -q → 278 passed, 1 deselected
```
