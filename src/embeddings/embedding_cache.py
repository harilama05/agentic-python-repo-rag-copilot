"""
Embedding cache — avoids re-computing embeddings for unchanged chunks.

Uses a simple on-disk JSON mapping from chunk_id → embedding vector.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.config import settings


class EmbeddingCache:
    """
    Simple disk-backed cache mapping ``chunk_id`` → ``List[float]``.

    This avoids expensive re-embedding when a file hasn't changed.
    """

    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir or settings.index_dir / "embedding_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self._cache_dir / "cache.json"
        self._data: Dict[str, List[float]] = {}
        self._load()

    def _load(self) -> None:
        if self._cache_file.exists():
            try:
                self._data = json.loads(self._cache_file.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self._cache_file.write_text(
            json.dumps(self._data), encoding="utf-8"
        )

    def get(self, chunk_id: str) -> Optional[List[float]]:
        return self._data.get(chunk_id)

    def put(self, chunk_id: str, embedding: List[float]) -> None:
        self._data[chunk_id] = embedding

    def has(self, chunk_id: str) -> bool:
        return chunk_id in self._data

    def clear(self) -> None:
        self._data.clear()
        if self._cache_file.exists():
            self._cache_file.unlink()

    @property
    def size(self) -> int:
        return len(self._data)
