"""
Agent tools — concrete implementations of tools the agent can call.

Each tool takes simple arguments and returns results that can be
serialised into the agent state.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.retrieval.retriever import Retriever
from src.storage.file_store import FileStore
from src.ingestion.file_loader import load_file_lines
from src.schemas import SearchResult


class AgentTools:
    """
    Provides the concrete tool implementations that the agent graph invokes.
    """

    def __init__(
        self,
        retriever: Retriever,
        file_store: FileStore,
        repo_root: str | Path,
    ):
        self.retriever = retriever
        self.file_store = file_store
        self.repo_root = Path(repo_root).resolve()

    def search_code(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Hybrid search over indexed chunks."""
        return self.retriever.search(query=query, top_k=top_k)

    def find_symbol(self, symbol_name: str) -> List[SearchResult]:
        """Direct symbol lookup by name."""
        return self.retriever.find_symbol(symbol_name)

    def find_references(
        self,
        symbol_name: str,
        max_results: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Find all references to a symbol by scanning Python files.

        Uses regex word-boundary matching for speed.
        """
        references: List[Dict[str, Any]] = []
        pattern = re.compile(rf"\b{re.escape(symbol_name)}\b")

        for file_path in self.repo_root.rglob("*.py"):
            if any(
                part in {".git", ".venv", "venv", "__pycache__"}
                for part in file_path.parts
            ):
                continue

            try:
                lines = file_path.read_text("utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for line_no, line in enumerate(lines, start=1):
                if not pattern.search(line):
                    continue

                stripped = line.strip()
                is_def = (
                    stripped.startswith(f"def {symbol_name}(")
                    or stripped.startswith(f"async def {symbol_name}(")
                    or stripped.startswith(f"class {symbol_name}(")
                    or stripped.startswith(f"class {symbol_name}:")
                )

                try:
                    rel = str(file_path.resolve().relative_to(self.repo_root))
                except ValueError:
                    rel = str(file_path)

                references.append({
                    "file_path": str(file_path.resolve()),
                    "relative_path": rel,
                    "line_number": line_no,
                    "line": line,
                    "is_definition": is_def,
                })

                if len(references) >= max_results:
                    return references

        return references

    def read_file(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read a file or line range from the repo."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path = path.resolve()

        try:
            rel = str(path.relative_to(self.repo_root))
        except ValueError:
            rel = str(path)

        content = load_file_lines(path, start_line, end_line)
        if content is None:
            return {"error": f"File not found: {path}"}

        all_lines = path.read_text("utf-8", errors="ignore").splitlines()
        return {
            "file_path": str(path),
            "relative_path": rel,
            "start_line": start_line or 1,
            "end_line": end_line or len(all_lines),
            "total_lines": len(all_lines),
            "content": content,
        }
