"""
File content store — keeps raw file contents in a lightweight JSON store
so the agent can read files without hitting disk every time.
"""

import json
from pathlib import Path
from typing import Dict, Optional

from src.config import settings


class FileStore:
    """
    Maps relative file paths to their raw text content.

    Useful for the ``read_file`` tool so it can serve content from memory
    after indexing, and also survives restarts via JSON persistence.
    """

    def __init__(self, persist_dir: Path | None = None):
        self._persist_dir = persist_dir or settings.metadata_persist_dir
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._store_file = self._persist_dir / "file_store.json"
        self._data: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._store_file.exists():
            try:
                self._data = json.loads(self._store_file.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self._store_file.write_text(
            json.dumps(self._data, ensure_ascii=False),
            encoding="utf-8",
        )

    def put(self, relative_path: str, content: str) -> None:
        self._data[relative_path] = content

    def get(self, relative_path: str) -> Optional[str]:
        return self._data.get(relative_path)

    def has(self, relative_path: str) -> bool:
        return relative_path in self._data

    def remove(self, relative_path: str) -> None:
        self._data.pop(relative_path, None)

    def clear(self) -> None:
        self._data.clear()

    @property
    def count(self) -> int:
        return len(self._data)
