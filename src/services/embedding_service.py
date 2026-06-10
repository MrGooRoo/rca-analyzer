"""
Локальный сервис эмбеддингов для поиска похожих инцидентов.

Почему локальный hashing-подход:
- не требует отдельного API-ключа и сетевых вызовов;
- детерминирован в тестах и в production;
- даёт быстрый baseline для RAG/поиска похожих случаев;
- позже может быть заменён на OpenRouter/внешнюю embedding-модель без смены API.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from src.domain.models import RCAResult

EMBEDDING_DIMENSION = 384
EMBEDDING_MODEL_NAME = "local/hash-ngrams-v1"

_TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)

# Небольшой список стоп-слов RU/EN, чтобы похожесть больше зависела
# от содержательных терминов: объект, действие, опасность, причина.
_STOP_WORDS: frozenset[str] = frozenset({
    "и", "в", "во", "на", "с", "со", "к", "ко", "по", "под", "над", "из", "за", "для",
    "от", "до", "при", "о", "об", "а", "но", "или", "что", "как", "это", "не", "нет",
    "был", "была", "были", "было", "его", "ее", "её", "их", "он", "она", "они", "мы",
    "вы", "ты", "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "from",
})


class EmbeddingService(Protocol):
    """Протокол embedding-провайдера."""

    model_name: str
    dimension: int

    def embed(self, text: str) -> list[float]:
        """Вернуть нормализованный dense-вектор фиксированной размерности."""


class LocalHashEmbeddingService:
    """
    Детерминированные эмбеддинги через feature hashing.

    Вектор строится по словам и символьным n-граммам. Это не заменяет
    полноценную семантическую модель, но хорошо работает как лёгкий baseline:
    тексты с общими объектами/опасностями/причинами получают большую cosine
    similarity, чем неродственные тексты.
    """

    model_name = EMBEDDING_MODEL_NAME
    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            self._add_feature(vector, f"tok:{token}", weight=1.0)

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
