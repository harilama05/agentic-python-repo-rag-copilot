"""
Metadata store — persists chunk metadata separately from the vector store.

This enables fast metadata-only lookups (e.g. symbol search by name)
without querying ChromaDB.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings


class MetadataStore:
    """
    Maps ``chunk_id`` → metadata dict.

    Supports lookups by symbol name, file path, etc.
    """

    def __init__(self, persist_dir: Path | None = None):
        self._persist_dir = persist_dir or settings.metadata_persist_dir
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._store_file = self._persist_dir / "chunk_metadata.json"
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._store_file.exists():
            try:
                self._data = json.loads(self._store_file.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self._store_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def add(self, chunk_id: str, metadata: Dict[str, Any]) -> None:
        self._data[chunk_id] = metadata

    def get(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get(chunk_id)

    def find_by_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all chunks whose ``symbol_name`` or ``qualified_name`` matches."""
        target = symbol_name.lower()
        results: List[Dict[str, Any]] = []

        for meta in self._data.values():
            name = str(meta.get("symbol_name", "")).lower()
            qname = str(meta.get("qualified_name", "")).lower()

            if target == name or target in qname:
                results.append(meta)

        return results

    def find_by_file(self, relative_path: str) -> List[Dict[str, Any]]:
        """Find all chunks from a specific file."""
        return [
            meta
            for meta in self._data.values()
            if meta.get("relative_path") == relative_path
        ]

    def clear(self) -> None:
        self._data.clear()

    @property
    def count(self) -> int:
        return len(self._data)
