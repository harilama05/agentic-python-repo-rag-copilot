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
from src.storage.graph_store import GraphStore
from src.ingestion.file_loader import load_file_lines
from src.schemas import SearchResult
from src.graph.code_graph import CodeNode


class AgentTools:
    """
    Provides the concrete tool implementations that the agent graph invokes.
    """

    def __init__(
        self,
        retriever: Retriever,
        file_store: FileStore,
        repo_root: str | Path,
        graph_store: Optional[GraphStore] = None,
    ):
        self.retriever = retriever
        self.file_store = file_store
        self.graph_store = graph_store
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
        Find callers/references to a symbol.

        Relationship queries use the code graph first. Regex scanning remains a
        fallback for repos that were indexed before the graph store existed.
        """
        graph_refs = self._find_graph_callers(symbol_name, max_results=max_results)
        if graph_refs:
            return graph_refs

        return self._find_references_by_regex(symbol_name, max_results=max_results)

    def find_callees(
        self,
        symbol_name: str,
        max_results: int = 30,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find symbols called by a function/method using the code graph."""
        if not self.graph_store:
            return {"sources": [], "callees": []}

        graph = self.graph_store.get_graph()
        result = graph.find_callees(symbol_name)
        return {
            "sources": [self._node_to_reference(node, True) for node in result["sources"]],
            "callees": [
                self._node_to_reference(node, False)
                for node in result["callees"][:max_results]
            ],
        }

    def impact_analysis(
        self,
        symbol_name: str,
        max_depth: int = 2,
        max_results: int = 30,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find callers that may be affected if a symbol changes."""
        if not self.graph_store:
            return {"targets": [], "affected": []}

        graph = self.graph_store.get_graph()
        result = graph.impact_analysis(symbol_name, max_depth=max_depth)
        return {
            "targets": [self._node_to_reference(node, True) for node in result["targets"]],
            "affected": [
                self._node_to_reference(node, False)
                for node in result["affected"][:max_results]
            ],
        }

    def _find_graph_callers(
        self,
        symbol_name: str,
        max_results: int = 30,
    ) -> List[Dict[str, Any]]:
        if not self.graph_store:
            return []

        graph = self.graph_store.get_graph()
        result = graph.find_callers(symbol_name)
        references: List[Dict[str, Any]] = [
            self._node_to_reference(node, False)
            for node in result["callers"][:max_results]
        ]
        return references[:max_results]

    def _node_to_reference(self, node: CodeNode, is_definition: bool) -> Dict[str, Any]:
        return {
            "chunk_id": node.chunk_id,
            "file_path": node.file_path,
            "relative_path": node.relative_path,
            "line_number": node.start_line,
            "start_line": node.start_line,
            "end_line": node.end_line,
            "line": f"{node.node_type} {node.qualified_name}",
            "symbol_name": node.name,
            "qualified_name": node.qualified_name,
            "symbol_type": node.node_type,
            "is_definition": is_definition,
            "source": "graph",
        }

    def _find_references_by_regex(
        self,
        symbol_name: str,
        max_results: int = 30,
    ) -> List[Dict[str, Any]]:
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
                    "start_line": line_no,
                    "end_line": line_no,
                    "line": line,
                    "is_definition": is_def,
                    "source": "regex",
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
