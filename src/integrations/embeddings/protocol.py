"""Protocol type для функции построения embedding-вектора.

Позволяет инъецировать embed_fn в RCARepository из use-case слоя,
устраняя прямую зависимость db → services.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias

# embed_fn(text) → (vector, model_name, dimension)
EmbeddingFn: TypeAlias = Callable[[str], Awaitable[tuple[list[float], str, int]]]
