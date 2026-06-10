"""
Локальный embedding-провайдер на предобученной HuggingFace-модели.

Зачем: вместо ручного словаря синонимов (local/hash-ngrams-v2) используем
готовую русскоязычную модель эмбеддингов, которая «из коробки» понимает,
что «упал со стремянки» и «падение с лестницы» — об одном и том же.

Модель по умолчанию — cointegrated/rubert-tiny2:
- 29M параметров, ~120MB на диске, быстрый инференс на CPU;
- лучший баланс качество/скорость для русского (бенчмарк encodechka);
- на наших HSE-кейсах: синонимы 0.67–0.73, несвязанные 0.37–0.48
  (разрыв ~0.25 — заметно лучше hash-baseline).

Особенности:
- transformers/torch — ОПЦИОНАЛЬНАЯ зависимость (extras `embeddings`):
  pip install -e ".[embeddings]"
  Если пакеты не установлены → EmbeddingServiceError, и RCARepository
  автоматически фолбэкается на local/hash-ngrams-v2.
- Модель скачивается с HF Hub при первом использовании и кэшируется
  в ~/.cache/huggingface (или HF_HOME). Без сети и без кэша → тоже фолбэк.
- Загрузка ленивая и потокобезопасная; инференс выполняется в thread pool
  (asyncio.to_thread), чтобы не блокировать event loop FastAPI.
- Вектор: mean pooling по attention mask → L2-нормализация → приведение
  к EMBEDDING_DIMENSION=384 (rubert-tiny2 даёт 312 → паддинг нулями,
  норма при этом сохраняется).

Переменные окружения:
    EMBEDDINGS_PROVIDER=huggingface   — включить этот провайдер (фабрика)
    HF_EMBEDDING_MODEL                — по умолчанию cointegrated/rubert-tiny2
    HF_EMBEDDING_MAX_TOKENS           — по умолчанию 512
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import threading

from src.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EmbeddingServiceError,
)

logger = logging.getLogger(__name__)

DEFAULT_HF_MODEL = "cointegrated/rubert-tiny2"

# Максимум символов на входе — страховка от огромных DOCX-описаний.
_MAX_INPUT_CHARS = 16_000


class HFLocalEmbeddingService:
    """
    Embedding-провайдер на локальной HuggingFace-модели.

    Контракт совпадает с LocalHashEmbeddingService (Protocol EmbeddingService),
    но embed() — корутина. Вектор всегда длины EMBEDDING_DIMENSION, нормализован.
    В result_embeddings.model_name пишется "hf/<model_id>".
    """

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.hf_model_id = model or os.getenv("HF_EMBEDDING_MODEL", DEFAULT_HF_MODEL)
        self.model_name = f"hf/{self.hf_model_id}"
        self.dimension = EMBEDDING_DIMENSION
        self.max_tokens = max_tokens or int(os.getenv("HF_EMBEDDING_MAX_TOKENS", "512"))

        self._tokenizer = None
        self._model = None
        self._load_lock = threading.Lock()
        self._load_error: Exception | None = None

        # Модели семейства E5 обучены с префиксами "query: " / "passage: ".
        # Для симметричного поиска похожих используем единый префикс query.
        self._input_prefix = "query: " if "e5" in self.hf_model_id.lower() else ""

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        prepared = (text or "").strip()[:_MAX_INPUT_CHARS]
        if not prepared:
            return [0.0] * self.dimension
        # Инференс CPU-bound → уводим из event loop.
        return await asyncio.to_thread(self.embed_sync, prepared)

    def embed_sync(self, text: str) -> list[float]:
        """Синхронный инференс (используется из embed() и скриптов)."""
        prepared = (text or "").strip()[:_MAX_INPUT_CHARS]
        if not prepared:
            return [0.0] * self.dimension

        self._ensure_model()
        raw = self._forward(self._input_prefix + prepared)
        return _fit_dimension(raw, self.dimension)

    # ------------------------------------------------------------------
    # Загрузка модели
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:
        """Лениво и потокобезопасно загрузить модель. Ошибка кэшируется."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if self._load_error is not None:
                # Не пытаемся загружать заново при каждом запросе.
                raise EmbeddingServiceError(
                    f"HF-модель {self.hf_model_id} недоступна: {self._load_error}"
                )
            try:
                import torch  # noqa: F401
                from transformers import AutoModel, AutoTokenizer
            except ImportError as exc:
                self._load_error = exc
                raise EmbeddingServiceError(
                    "Пакеты torch/transformers не установлены. "
                    'Установите extras: pip install -e ".[embeddings]"'
                ) from exc

            try:
                logger.info("[HF Embeddings] загрузка модели %s ...", self.hf_model_id)
                tokenizer = AutoTokenizer.from_pretrained(self.hf_model_id)
                model = AutoModel.from_pretrained(self.hf_model_id)
                model.eval()
            except Exception as exc:  # сеть/диск/повреждённый кэш
                self._load_error = exc
                raise EmbeddingServiceError(
                    f"Не удалось загрузить HF-модель {self.hf_model_id}: {exc}"
                ) from exc

            self._tokenizer = tokenizer
            self._model = model
            logger.info("[HF Embeddings] модель %s готова", self.hf_model_id)

    # ------------------------------------------------------------------
    # Инференс
    # ------------------------------------------------------------------

    def _forward(self, text: str) -> list[float]:
        import torch

        try:
            with torch.no_grad():
                encoded = self._tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self.max_tokens,
                )
                output = self._model(**encoded)
                # Mean pooling по attention mask + L2-нормализация.
                mask = encoded["attention_mask"].unsqueeze(-1).float()
                vector = (output.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                vector = torch.nn.functional.normalize(vector, dim=-1)
                return vector[0].tolist()
        except Exception as exc:
            raise EmbeddingServiceError(
                f"Ошибка инференса HF-модели {self.hf_model_id}: {exc}"
            ) from exc


def _fit_dimension(vector: list[float], dimension: int) -> list[float]:
    """
    Привести вектор к целевой размерности и L2-нормализовать.

    rubert-tiny2 даёт 312 → дополняем нулями до 384 (норма сохраняется).
    Модели с большей размерностью усекаются (первые N компонент).
    """
    if len(vector) > dimension:
        vector = vector[:dimension]
    elif len(vector) < dimension:
        vector = vector + [0.0] * (dimension - len(vector))

    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]
