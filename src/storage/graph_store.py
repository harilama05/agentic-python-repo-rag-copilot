"""
JSON-backed store for the lightweight code graph.
"""

import json
from pathlib import Path
from typing import Optional

from src.config import settings
from src.graph.code_graph import CodeGraph


class GraphStore:
    def __init__(self, persist_dir: str | Path | None = None):
        self._persist_dir = Path(persist_dir or settings.graph_persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._store_file = self._persist_dir / "code_graph.json"
        self._graph = CodeGraph()
        self._load()

    def _load(self) -> None:
        if not self._store_file.exists():
            return

        try:
            data = json.loads(self._store_file.read_text("utf-8"))
            self._graph = CodeGraph.from_dict(data)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            self._graph = CodeGraph()

    def save(self) -> None:
        self._store_file.write_text(
            json.dumps(self._graph.to_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def set_graph(self, graph: CodeGraph) -> None:
        self._graph = graph

    def get_graph(self) -> CodeGraph:
        return self._graph

    def clear(self) -> None:
        self._graph = CodeGraph()
        if self._store_file.exists():
            self._store_file.unlink()

    @property
    def count(self) -> int:
        return len(self._graph.nodes)
