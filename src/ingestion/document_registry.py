"""
Tracks which files/documents have been indexed.

Prevents re-indexing unchanged files (incremental indexing support).
Uses a simple JSON-based persistence layer.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone

from src.config import settings


class DocumentRegistry:
    """
    Registry that maps file paths to their last-indexed hash and timestamp.

    Stored as a JSON file inside ``metadata_persist_dir``.
    """

    def __init__(self, persist_path: Optional[Path] = None):
        self._persist_path = persist_path or (
            settings.metadata_persist_dir / "document_registry.json"
        )
        self._records: Dict[str, dict] = {}
        self._load()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                self._records = json.loads(self._persist_path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._records = {}

    def save(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_path.write_text(
            json.dumps(self._records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Hash helpers ─────────────────────────────────────────────────

    @staticmethod
    def _file_hash(file_path: Path) -> str:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    # ── Public API ───────────────────────────────────────────────────

    def is_indexed(self, file_path: str | Path) -> bool:
        """Check whether a file has already been indexed."""
        key = str(Path(file_path).resolve())
        return key in self._records

    def needs_reindex(self, file_path: str | Path) -> bool:
        """Return True if the file is new or has changed since last index."""
        path = Path(file_path).resolve()
        key = str(path)

        if key not in self._records:
            return True

        current_hash = self._file_hash(path)
        return self._records[key].get("hash") != current_hash

    def mark_indexed(self, file_path: str | Path, chunk_count: int = 0) -> None:
        """Record that a file has been indexed."""
        path = Path(file_path).resolve()
        key = str(path)

        self._records[key] = {
            "hash": self._file_hash(path),
            "chunk_count": chunk_count,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }

    def remove(self, file_path: str | Path) -> None:
        key = str(Path(file_path).resolve())
        self._records.pop(key, None)

    def clear(self) -> None:
        self._records.clear()

    @property
    def count(self) -> int:
        return len(self._records)
