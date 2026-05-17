import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.retriever import CodeRetriever, CodeSearchResult

from src.reranker import CrossEncoderReranker, NoOpReranker
from src.settings import (
    CROSS_ENCODER_CANDIDATE_K,
    DEFAULT_TOP_K,
    RETRIEVAL_MODE_ACCURATE,
    RETRIEVAL_MODE_FAST,
)

from src.constants import IGNORE_DIRS, PYTHON_EXTENSIONS

from src.code_graph import CodeGraph, CodeNode

def format_search_result(result: CodeSearchResult) -> Dict[str, Any]:
    metadata = result.metadata

    return {
        "chunk_id": result.chunk_id,
        "source_type": metadata.get("source_type"),
        "file_path": metadata.get("file_path"),
        "relative_path": metadata.get("relative_path"),
        "symbol_name": metadata.get("symbol_name"),
        "qualified_name": metadata.get("qualified_name"),
        "symbol_type": metadata.get("symbol_type"),
        "heading": metadata.get("heading"),
        "start_line": metadata.get("start_line"),
        "end_line": metadata.get("end_line"),
        "final_score": result.final_score,
        "vector_score": result.vector_score,
        "bm25_score": result.bm25_score,
        "keyword_score": result.keyword_score,
        "symbol_score": result.symbol_score,
        "text": result.text,
    }

def format_graph_node(node: CodeNode, node_role: str = "node") -> Dict[str, Any]:
    return {
        "node_id": node.node_id,
        "role": node_role,
        "relative_path": node.relative_path,
        "line_start": node.start_line,
        "line_end": node.end_line,
        "symbol": node.qualified_name,
        "type": node.node_type,
    }

class CodebaseTools:
    def __init__(
        self,
        retriever: CodeRetriever,
        repo_root: str | Path,
        retrieval_mode: str = RETRIEVAL_MODE_FAST,
        code_graph: CodeGraph | None = None,
    ):
        self.retriever = retriever
        self.repo_root = Path(repo_root).resolve()
        self.retrieval_mode = retrieval_mode
        self.code_graph = code_graph or CodeGraph()

        if retrieval_mode == RETRIEVAL_MODE_ACCURATE:
            self.reranker = CrossEncoderReranker()
        else:
            self.reranker = NoOpReranker()

    def search_code(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
        """
        Search indexed repository chunks using hybrid retrieval.
        This can return both code and documentation chunks.
        """
        if self.retrieval_mode == RETRIEVAL_MODE_ACCURATE:
            candidate_k = max(CROSS_ENCODER_CANDIDATE_K, top_k)
        else:
            candidate_k = top_k

        raw_results = self.retriever.search_code(
            query=query,
            top_k=candidate_k,
        )

        formatted_results = [
            format_search_result(result)
            for result in raw_results
        ]

        if self.retrieval_mode == RETRIEVAL_MODE_ACCURATE:
            return self.reranker.rerank(
                query=query,
                results=formatted_results,
                top_k=top_k,
            )

        return formatted_results[:top_k]

    def find_symbol(self, symbol_name: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Find functions/classes/methods by symbol name.

        This uses the retriever, then applies stronger filtering by metadata.
        """
        results = self.retriever.search_code(
            query=symbol_name,
            top_k=top_k,
            candidate_k=50,
        )

        formatted_results = []

        target = symbol_name.lower()

        for result in results:
            metadata = result.metadata

            current_symbol = str(metadata.get("symbol_name", "")).lower()
            qualified_name = str(metadata.get("qualified_name", "")).lower()

            if target == current_symbol or target in qualified_name:
                formatted_results.append(format_search_result(result))

        return formatted_results

    def read_file(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        context_lines: int = 0,
    ) -> Dict[str, Any]:
        """
        Read a file or line range from the repo.

        file_path can be absolute or relative to repo_root.
        """
        path = Path(file_path)

        if not path.is_absolute():
            path = self.repo_root / path

        path = path.resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        try:
            relative_path = str(path.relative_to(self.repo_root))
        except ValueError:
            relative_path = str(path)

        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

        total_lines = len(lines)

        if start_line is None:
            start_line = 1

        if end_line is None:
            end_line = total_lines

        start_line = max(1, int(start_line) - context_lines)
        end_line = min(total_lines, int(end_line) + context_lines)

        selected_lines = lines[start_line - 1:end_line]

        numbered_text = "\n".join(
            f"{line_no}: {line}"
            for line_no, line in enumerate(selected_lines, start=start_line)
        )

        return {
            "file_path": str(path),
            "relative_path": relative_path,
            "start_line": start_line,
            "end_line": end_line,
            "total_lines": total_lines,
            "content": numbered_text,
        }
    
    def find_references(
        self,
        symbol_name: str,
        include_definition: bool = True,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Find references to a symbol by scanning Python files.

        This is a lightweight reference search.
        It looks for exact symbol usage in .py files.
        """
        references: List[Dict[str, Any]] = []

        pattern = re.compile(rf"\b{re.escape(symbol_name)}\b")

        for file_path in self.repo_root.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in PYTHON_EXTENSIONS:
                continue

            if any(part in IGNORE_DIRS for part in file_path.parts):
                continue

            try:
                lines = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines()
            except Exception:
                continue

            for line_number, line in enumerate(lines, start=1):
                if not pattern.search(line):
                    continue

                stripped = line.strip()

                is_definition = (
                    stripped.startswith(f"def {symbol_name}(")
                    or stripped.startswith(f"async def {symbol_name}(")
                    or stripped.startswith(f"class {symbol_name}(")
                    or stripped.startswith(f"class {symbol_name}:")
                )

                if is_definition and not include_definition:
                    continue

                try:
                    relative_path = str(file_path.resolve().relative_to(self.repo_root))
                except ValueError:
                    relative_path = str(file_path)

                references.append(
                    {
                        "file_path": str(file_path.resolve()),
                        "relative_path": relative_path,
                        "line_number": line_number,
                        "line": line,
                        "is_definition": is_definition,
                    }
                )

                if len(references) >= max_results:
                    return references

        return references
    
    def find_callers(self, symbol_name: str) -> Dict[str, Any]:
        """
        Find functions/methods that call the given symbol.
        """
        result = self.code_graph.find_callers(symbol_name)

        return {
            "symbol": symbol_name,
            "targets": [
                format_graph_node(node, node_role="target")
                for node in result["targets"]
            ],
            "callers": [
                format_graph_node(node, node_role="caller")
                for node in result["callers"]
            ],
        }
    
    def find_callees(self, symbol_name: str) -> Dict[str, Any]:
        """
        Find functions/methods called by the given symbol.
        """
        result = self.code_graph.find_callees(symbol_name)

        return {
            "symbol": symbol_name,
            "sources": [
                format_graph_node(node, node_role="source")
                for node in result["sources"]
            ],
            "callees": [
                format_graph_node(node, node_role="callee")
                for node in result["callees"]
            ],
        }
    
    def impact_analysis(self, symbol_name: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Find code nodes that may be affected if a symbol changes or is removed.
        """
        result = self.code_graph.impact_analysis(
            symbol=symbol_name,
            max_depth=max_depth,
        )

        return {
            "symbol": symbol_name,
            "targets": [
                format_graph_node(node, node_role="target")
                for node in result["targets"]
            ],
            "affected": [
                format_graph_node(node, node_role="affected")
                for node in result["affected"]
            ],
        }