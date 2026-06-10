"""
Сервисы эмбеддингов для поиска похожих инцидентов.

Три провайдера (выбор через env `EMBEDDINGS_PROVIDER`):

1. `local` (по умолчанию) — `LocalHashEmbeddingService`, модель `local/hash-ngrams-v2`:
   - детерминированный feature hashing без внешних API и зависимостей;
   - v2: лёгкий русский стемминг + словарь HSE-синонимов, поэтому
     «упал со стремянки» и «падение с лестницы» получают высокую похожесть.

2. `huggingface` — `HFLocalEmbeddingService` (см. src/integrations/embeddings/hf_local.py):
   - локальная предобученная модель (default cointegrated/rubert-tiny2, 29M, CPU);
   - настоящая семантика без внешних API в рантайме; модель скачивается
     один раз с HF Hub и кэшируется на диске;
   - требует extras: pip install -e ".[embeddings]".

3. `openrouter` — `OpenRouterEmbeddingService` (см. src/integrations/llm/openrouter_embeddings.py):
   - настоящая семантическая модель через POST /embeddings OpenRouter;
   - платные запросы, требуется OPENROUTER_API_KEY.

При ошибке внешнего/тяжёлого провайдера (`EmbeddingServiceError`) репозиторий
автоматически откатывается на локальный hashing-сервис (вектор сохраняется
с локальным model_name, чтобы не смешивать пространства разных моделей).

Контракт хранения: вектор всегда размерности EMBEDDING_DIMENSION (384),
нормализованный; в `result_embeddings.model_name` пишется модель, которая
реально построила вектор. Поиск сравнивает только векторы одной модели.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections.abc import Awaitable
from typing import Protocol

from src.domain.models import RCAResult

EMBEDDING_DIMENSION = 384
EMBEDDING_MODEL_NAME = "local/hash-ngrams-v2"

_TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)

# Небольшой список стоп-слов RU/EN, чтобы похожесть больше зависела
# от содержательных терминов: объект, действие, опасность, причина.
_STOP_WORDS: frozenset[str] = frozenset({
    "и", "в", "во", "на", "с", "со", "к", "ко", "по", "под", "над", "из", "за", "для",
    "от", "до", "при", "о", "об", "а", "но", "или", "что", "как", "это", "не", "нет",
    "был", "была", "были", "было", "его", "ее", "её", "их", "он", "она", "они", "мы",
    "вы", "ты", "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "from",
})

# ---------------------------------------------------------------------------
# Лёгкий русский стемминг (v2)
# ---------------------------------------------------------------------------

# Окончания отсортированы по длине (сначала длинные), чтобы снимать самое
# специфичное. Это не полный Snowball, а дешёвая аппроксимация для feature
# hashing: цель — чтобы «лестница/лестницы/лестнице» давали один stem-признак.
_RU_SUFFIXES: tuple[str, ...] = tuple(sorted({
    # существительные
    "иями", "ями", "ами", "иях", "ях", "ах", "ием", "ьей",
    "ия", "ие", "ий", "ии", "ью", "ья", "ье",
    "ов", "ев", "ей", "ом", "ем", "ам", "ям", "ой", "ою", "ею",
    "а", "я", "о", "е", "и", "ы", "у", "ю", "ь",
    # прилагательные / причастия
    "ыми", "ими", "ого", "его", "ому", "ему", "ая", "яя", "ое", "ее", "ый", "ых", "их", "ую", "юю",
    "ший", "щий", "шей", "щей", "вший", "вшая", "вшее", "вшие",
    # глаголы
    "ировать", "овать", "евать", "ывать", "ивать",
    "ться", "тся", "лся", "лась", "лось", "лись",
    "ешь", "ишь", "ете", "ите", "ует", "уют", "яет", "яют",
    "ает", "ают", "ит", "ат", "ят", "ет", "ют", "ти", "ть",
    "ла", "ло", "ли", "л",
    # наречия / отглагольные
    "ение", "ением", "ении", "ений", "ация", "ацией", "ости", "ость",
}, key=len, reverse=True))

_MIN_STEM_LEN = 4


def _stem_ru(token: str) -> str:
    """Снять одно самое длинное окончание, если остаток >= _MIN_STEM_LEN символов."""
    for suffix in _RU_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM_LEN:
            return token[: len(token) - len(suffix)]
    return token


# ---------------------------------------------------------------------------
# Словарь HSE-концептов (v2)
# ---------------------------------------------------------------------------

# concept -> префиксы стемов, которые на него отображаются.
# Если стем токена начинается с одного из префиксов, в вектор добавляется
# общий признак концепта. Так «стремянка» и «лестница» получают общий признак
# "concept:ladder", даже без общих слов и n-грамм.
_CONCEPT_PREFIXES: dict[str, tuple[str, ...]] = {
    "fall":        ("паден", "падал", "упал", "упад", "поскользн", "скольз", "оступ",
                    "сорвал", "срыв", "свалил"),
    "ladder":      ("лестниц", "стремянк", "трап", "ступен", "пристав"),
    "height":      ("высот", "леса", "лесов", "подмост", "кровл", "крыш"),
    "slippery":    ("мокр", "влажн", "гололед", "налед", "масл", "разлит"),
    "injury":      ("травм", "ушиб", "перелом", "ранен", "поврежден", "вывих", "порез", "ампутац"),
    "burn":        ("ожог", "ожег", "обожг", "терм", "горяч", "кипят", "пар"),
    "fire":        ("пожар", "возгоран", "загорел", "огн", "плам", "задымлен", "дым"),
    "electricity": ("электр", "ток", "напряжен", "замыкан", "кабел", "провод", "щит"),
    "equipment":   ("оборудован", "станок", "станк", "механизм", "агрегат", "устройств",
                    "машин", "установк"),
    "vehicle":     ("автомобил", "транспорт", "погрузчик", "самосвал", "автобус", "наезд", "дтп"),
    "crane":       ("кран", "подъемн", "стропальн", "строп", "груз", "такелаж"),
    "chemical":    ("химич", "кислот", "щелоч", "реагент", "токсичн", "отравлен",
                    "вещств", "веществ"),
    "gas":         ("газ", "утечк", "метан", "пропан", "угарн", "загазован"),
    "ppe":         ("сиз", "каск", "перчатк", "очк", "респиратор", "страховочн", "привяз"),
    "training":    ("инструктаж", "обучен", "стажировк", "допуск", "квалификац", "наряд"),
    "maintenance": ("ремонт", "обслуживан", "неисправн", "износ", "дефект", "отказ", "поломк"),
    "fatality":    ("смерт", "погиб", "летальн", "гибел"),
}


def _concepts_for(stem: str) -> list[str]:
    return [
        concept
        for concept, prefixes in _CONCEPT_PREFIXES.items()
        if any(stem.startswith(p) for p in prefixes)
    ]


# ---------------------------------------------------------------------------
# Протокол и реализации
# ---------------------------------------------------------------------------

class EmbeddingServiceError(Exception):
    """Ошибка построения embedding (сеть, API, формат ответа)."""


class EmbeddingService(Protocol):
    """Протокол embedding-провайдера. embed может быть sync или async."""

    model_name: str
    dimension: int

    def embed(self, text: str) -> list[float] | Awaitable[list[float]]:
        """Вернуть нормализованный dense-вектор фиксированной размерности."""


class LocalHashEmbeddingService:
    """
    Детерминированные эмбеддинги через feature hashing (v2).

    Признаки на токен:
    - tok:<token>      — само слово (вес 1.0)
    - stem:<stem>      — русский стем (вес 0.9) → сближает словоформы
    - concept:<name>   — HSE-концепт из словаря (вес 1.6) → сближает синонимы
    - tri:/quad:       — символьные n-граммы (0.35 / 0.20) → морфология и опечатки
    """

    model_name = EMBEDDING_MODEL_NAME
    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            self._add_feature(vector, f"tok:{token}", weight=1.0)

            stem = _stem_ru(token)
            if stem != token:
                self._add_feature(vector, f"stem:{stem}", weight=0.9)

            for concept in _concepts_for(stem):
                self._add_feature(vector, f"concept:{concept}", weight=1.6)

            # Символьные n-граммы помогают русской морфологии:
            # «лестница», «лестницы», «лестнице» будут ближе.
            if len(token) >= 4:
                for ngram in self._char_ngrams(token, n=3):
                    self._add_feature(vector, f"tri:{ngram}", weight=0.35)
            if len(token) >= 6:
                for ngram in self._char_ngrams(token, n=4):
                    self._add_feature(vector, f"quad:{ngram}", weight=0.20)

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens = [m.group(0).lower().replace("ё", "е") for m in _TOKEN_RE.finditer(text or "")]
        return [t for t in tokens if len(t) > 1 and t not in _STOP_WORDS]

    @staticmethod
    def _char_ngrams(token: str, n: int) -> list[str]:
        if len(token) < n:
            return []
        return [token[i:i + n] for i in range(len(token) - n + 1)]

    def _add_feature(self, vector: list[float], feature: str, *, weight: float) -> None:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, byteorder="big", signed=False)
        index = raw % self.dimension
        sign = 1.0 if ((raw >> 63) & 1) == 0 else -1.0
        vector[index] += sign * weight


# ---------------------------------------------------------------------------
# Фабрика провайдера
# ---------------------------------------------------------------------------

_service_cache: dict[str, EmbeddingService] = {}


def get_embedding_service() -> EmbeddingService:
    """
    Вернуть embedding-сервис согласно окружению.

    EMBEDDINGS_PROVIDER=local       → LocalHashEmbeddingService (по умолчанию)
    EMBEDDINGS_PROVIDER=huggingface → HFLocalEmbeddingService
                                      (локальная предобученная модель,
                                      HF_EMBEDDING_MODEL, default rubert-tiny2)
    EMBEDDINGS_PROVIDER=openrouter  → OpenRouterEmbeddingService
                                      (модель из OPENROUTER_EMBEDDING_MODEL)

    Экземпляры кэшируются по ключу provider+model.
    """
    provider = os.getenv("EMBEDDINGS_PROVIDER", "local").strip().lower()

    if provider in ("huggingface", "hf"):
        from src.integrations.embeddings.hf_local import (
            DEFAULT_HF_MODEL,
            HFLocalEmbeddingService,
        )
        model = os.getenv("HF_EMBEDDING_MODEL", DEFAULT_HF_MODEL).strip()
        cache_key = f"huggingface:{model}"
        if cache_key not in _service_cache:
            _service_cache[cache_key] = HFLocalEmbeddingService(model=model)
        return _service_cache[cache_key]

    if provider == "openrouter":
        from src.integrations.llm.openrouter_embeddings import (
            DEFAULT_EMBEDDING_MODEL,
            OpenRouterEmbeddingService,
        )
        model = os.getenv("OPENROUTER_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
        cache_key = f"openrouter:{model}"
        if cache_key not in _service_cache:
            _service_cache[cache_key] = OpenRouterEmbeddingService(model=model)
        return _service_cache[cache_key]

    cache_key = "local"
    if cache_key not in _service_cache:
        _service_cache[cache_key] = LocalHashEmbeddingService()
    return _service_cache[cache_key]


def reset_embedding_service_cache() -> None:
    """Сбросить кэш фабрики (используется в тестах при смене env)."""
    _service_cache.clear()


def default_similarity_threshold() -> float:
    """
    Дефолтный порог похожести для текущего провайдера.

    У hashing-эмбеддингов несвязанные тексты дают similarity ~0, поэтому
    порог низкий. У нейросетевых моделей (HF/OpenRouter) даже несвязанные
    тексты дают ~0.4–0.5, поэтому порог выше.

    Переопределяется через env SIMILARITY_THRESHOLD.
    """
    env_value = os.getenv("SIMILARITY_THRESHOLD", "").strip()
    if env_value:
        try:
            return max(0.0, min(1.0, float(env_value)))
        except ValueError:
            pass

    provider = os.getenv("EMBEDDINGS_PROVIDER", "local").strip().lower()
    if provider in ("huggingface", "hf", "openrouter"):
        return 0.55
    return 0.15


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity для уже нормализованных или обычных векторов."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def build_result_embedding_text(result: RCAResult) -> str:
    """Собрать текст результата RCA, который индексируется для похожести."""
    parts: list[str] = [
        f"Методология: {result.methodology.value}",
        result.summary,
    ]

    for title, nodes in (
        ("Корневые причины", result.root_causes),
        ("Способствующие причины", result.contributing_causes),
        ("Непосредственные причины", result.immediate_causes),
    ):
        if nodes:
            parts.append(title)
            parts.extend(node.text for node in nodes if node.text)

    if result.recommendations:
        parts.append("Рекомендации")
        parts.extend(rec.text for rec in result.recommendations if rec.text)

    return "\n".join(part for part in parts if part).strip()
