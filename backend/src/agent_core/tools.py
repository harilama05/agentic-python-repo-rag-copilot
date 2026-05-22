"""Agent tool façade for retrieval, graph, and file reading.

This module keeps transport layers and the main agent decoupled from the
underlying retriever, graph, and reranking implementations.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.constants import (
    DOC_EXTENSIONS,
    IGNORE_DIRS,
    JSON_EXTENSIONS,
    PYTHON_EXTENSIONS,
    TEXT_EXTENSIONS,
)
from src.graph.code_graph import CodeGraph, CodeNode
from src.reranking.cross_encoder_reranker import CrossEncoderReranker
from src.reranking.reranker import NoOpReranker
from src.retrieval.retriever import CodeRetriever, CodeSearchResult
from src.core.settings import (
    CROSS_ENCODER_CANDIDATE_K,
    DEFAULT_CANDIDATE_K,
    DEFAULT_TOP_K,
    RETRIEVAL_MODE_ACCURATE,
    RETRIEVAL_MODE_FAST,
)


def format_search_result(result: CodeSearchResult) -> Dict[str, Any]:
    """Format a retriever result into the stable public search schema."""
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


def normalize_source(
    *,
    relative_path: str,
    line_start: int | None,
    line_end: int | None,
    symbol: str | None = None,
    source_type: str | None = None,
    source_role: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Normalize source metadata for UI/API citations."""
    source: Dict[str, Any] = {
        "relative_path": str(relative_path or "").replace("\\", "/"),
        "line_start": line_start,
        "line_end": line_end,
        "symbol": symbol,
        "type": source_type,
    }

    if source_role:
        source["source_role"] = source_role
        source["role"] = source_role

    if extra:
        source.update(extra)

    return source


def format_graph_node(node: CodeNode, node_role: str = "node") -> Dict[str, Any]:
    """Serialize a graph node into the app's stable citation schema."""
    return normalize_source(
        relative_path=node.relative_path,
        line_start=node.start_line,
        line_end=node.end_line,
        symbol=node.qualified_name,
        source_type=node.node_type,
        source_role=node_role,
        extra={
            "node_id": node.node_id,
            "name": node.name,
            "qualified_name": node.qualified_name,
            "parent": getattr(node, "parent", None),
        },
    )


class CodebaseTools:
    """Repository-scoped tool façade used by the agent."""

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

    def resolve_graph_symbols(
        self,
        symbol_name: str,
        max_candidates: int = 10,
    ) -> List[CodeNode]:
        """Resolve a user-provided symbol into graph nodes."""
        query = symbol_name.strip()
        query_lower = query.lower()

        exact_qualified: List[CodeNode] = []
        exact_name: List[CodeNode] = []
        suffix_match: List[CodeNode] = []

        for node in self.code_graph.nodes.values():
            qualified_name = str(node.qualified_name or "")
            name = str(node.name or "")
            qualified_lower = qualified_name.lower()
            name_lower = name.lower()

            if qualified_lower == query_lower:
                exact_qualified.append(node)
            elif name_lower == query_lower:
                exact_name.append(node)
            elif qualified_lower.endswith(f".{query_lower}"):
                suffix_match.append(node)

        if exact_qualified:
            return exact_qualified[:max_candidates]

        if exact_name:
            return exact_name[:max_candidates]

        return suffix_match[:max_candidates]

    def _build_ambiguous_symbol_response(
        self,
        symbol_name: str,
        candidates: List[CodeNode],
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol_name,
            "resolved_symbol": None,
            "ambiguous": True,
            "message": (
                f"Multiple symbols match '{symbol_name}'. "
                "Use a more qualified name to disambiguate."
            ),
            "candidates": [
                format_graph_node(candidate, node_role="candidate")
                for candidate in candidates
            ],
        }

    def search_code(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        query_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Search indexed chunks using hybrid retrieval and optional reranking."""
        if self.retrieval_mode == RETRIEVAL_MODE_ACCURATE:
            candidate_k = max(CROSS_ENCODER_CANDIDATE_K, DEFAULT_CANDIDATE_K, top_k)
        else:
            candidate_k = max(DEFAULT_CANDIDATE_K, top_k)

        raw_results = self.retriever.search_code(
            query=query,
            top_k=candidate_k,
            query_type=query_type,
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
        """Find likely symbol definitions by symbol name."""
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

    def find_definitions(self, symbol_name: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Find symbol definitions in normalized source schema."""
        results = self.find_symbol(symbol_name=symbol_name, top_k=top_k)

        definitions = []

        for result in results:
            definitions.append(
                normalize_source(
                    relative_path=result.get("relative_path") or result.get("file_path") or "",
                    line_start=result.get("start_line") or result.get("line_start"),
                    line_end=result.get("end_line") or result.get("line_end"),
                    symbol=result.get("qualified_name") or result.get("symbol_name"),
                    source_type=result.get("symbol_type"),
                    source_role="definition",
                    extra=result,
                )
            )

        return definitions

    @staticmethod
    def _extract_chunk_code(text: str) -> str:
        """Strip metadata headers from chunk text, returning only the source content.

        Code chunks use ``\nCode:\n`` as separator, documentation chunks use
        ``\nContent:\n``.  Text/JSON chunks have no header at all.
        Handles both ``\n`` and ``\r\n`` line endings.
        """
        normalized = str(text).replace("\r\n", "\n")

        # Code chunks (from code_chunker)
        if "\nCode:\n" in normalized:
            return normalized.split("\nCode:\n", 1)[1]

        # Documentation chunks (from markdown_chunker)
        if "\nContent:\n" in normalized:
            return normalized.split("\nContent:\n", 1)[1]

        # Text/JSON chunks have no wrapper — return as-is
        return normalized

    def _get_chunk_meta(self, chunk):
        """Extract (relative_path, start_line, end_line, code_text) from a chunk."""
        meta = chunk if isinstance(chunk, dict) else getattr(chunk, "metadata", {})
        if isinstance(chunk, dict) and "metadata" in chunk:
            meta = chunk["metadata"]

        p = (
            (chunk.get("relative_path") if isinstance(chunk, dict) else getattr(chunk, "relative_path", None))
            or meta.get("relative_path")
            or meta.get("file_path")
        )

        start = (
            (chunk.get("start_line") if isinstance(chunk, dict) else getattr(chunk, "start_line", None))
            or meta.get("start_line")
            or meta.get("line_start")
            or 1
        )

        end = (
            (chunk.get("end_line") if isinstance(chunk, dict) else getattr(chunk, "end_line", None))
            or meta.get("end_line")
            or meta.get("line_end")
            or 0
        )

        text = (
            (chunk.get("text") if isinstance(chunk, dict) else getattr(chunk, "text", None))
            or meta.get("text")
            or ""
        )

        return str(p or ""), int(start), int(end), self._extract_chunk_code(text)

    def _read_file_from_db(self, relative_path: str) -> List[str]:
        target_path = str(relative_path).replace("\\", "/")
        lines_dict = {}

        for chunk in self.retriever.indexed_chunks:
            p, start, _end, code_text = self._get_chunk_meta(chunk)
            if not p or str(p).replace("\\", "/") != target_path:
                continue

            for i, line in enumerate(code_text.splitlines()):
                lines_dict[start + i] = line

        if not lines_dict:
            raise FileNotFoundError(f"File not found in database: {relative_path}")

        max_line = max(lines_dict.keys())
        return [lines_dict.get(i, "") for i in range(1, max_line + 1)]

    def read_file(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        context_lines: int = 0,
    ) -> Dict[str, Any]:
        """Read a file or line range relative to the indexed repository root."""
        path = Path(file_path)

        if not path.is_absolute():
            relative_path = str(path).replace("\\", "/")
        else:
            try:
                relative_path = str(path.resolve().relative_to(self.repo_root.resolve())).replace("\\", "/")
            except ValueError:
                relative_path = str(path).replace("\\", "/")

        lines = self._read_file_from_db(relative_path)

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

    def _find_references_in_db(self, patterns: list, short_symbol: str, include_definition: bool, symbol_name: str, max_results: int) -> List[Dict[str, Any]]:
        references = []
        for chunk in self.retriever.indexed_chunks:
            p, start, _end, code_text = self._get_chunk_meta(chunk)
            if not p:
                continue

            relative_path = str(p).replace("\\", "/")
            if not any(relative_path.endswith(ext) for ext in PYTHON_EXTENSIONS):
                continue

            for i, line in enumerate(code_text.splitlines()):
                if not any(pattern.search(line) for pattern in patterns):
                    continue
                
                stripped = line.strip()
                is_definition = (
                    stripped.startswith(f"def {short_symbol}(")
                    or stripped.startswith(f"async def {short_symbol}(")
                    or stripped.startswith(f"class {short_symbol}(")
                    or stripped.startswith(f"class {short_symbol}:")
                )
                
                if is_definition and not include_definition:
                    continue
                    
                reference_type = "definition" if is_definition else "reference"
                line_number = start + i
                
                # Check if we already added this reference from an overlapping chunk
                if any(r["relative_path"] == relative_path and r["line_start"] == line_number for r in references):
                    continue

                references.append(
                    normalize_source(
                        relative_path=relative_path,
                        line_start=line_number,
                        line_end=line_number,
                        symbol=symbol_name,
                        source_type=reference_type,
                        source_role=reference_type,
                        extra={
                            "line_number": line_number,
                            "line": line,
                            "is_definition": is_definition,
                            "reference_type": reference_type,
                        },
                    )
                )

                if len(references) >= max_results:
                    return references
        return references

    def find_references(
        self,
        symbol_name: str,
        include_definition: bool = False,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Find lexical symbol references by scanning repository Python files."""
        references: List[Dict[str, Any]] = []
        symbol_name = symbol_name.strip()

        if not symbol_name:
            return references

        short_symbol = symbol_name.split(".")[-1]
        patterns = [re.compile(rf"\b{re.escape(short_symbol)}\b")]

        if "." in symbol_name:
            patterns.append(re.compile(re.escape(symbol_name)))

        return self._find_references_in_db(patterns, short_symbol, include_definition, symbol_name, max_results)

    def find_callers(self, symbol_name: str) -> Dict[str, Any]:
        """Find functions or methods that call the given symbol."""
        candidates = self.resolve_graph_symbols(symbol_name)

        if len(candidates) > 1:
            return self._build_ambiguous_symbol_response(symbol_name, candidates)

        resolved_symbol = candidates[0].qualified_name if candidates else symbol_name
        result = self.code_graph.find_callers(resolved_symbol)

        return {
            "symbol": symbol_name,
            "resolved_symbol": resolved_symbol,
            "ambiguous": False,
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
        """Find functions or methods called by the given symbol."""
        candidates = self.resolve_graph_symbols(symbol_name)

        if len(candidates) > 1:
            return self._build_ambiguous_symbol_response(symbol_name, candidates)

        resolved_symbol = candidates[0].qualified_name if candidates else symbol_name
        result = self.code_graph.find_callees(resolved_symbol)

        return {
            "symbol": symbol_name,
            "resolved_symbol": resolved_symbol,
            "ambiguous": False,
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
        """Find code nodes that may be affected if a symbol changes."""
        candidates = self.resolve_graph_symbols(symbol_name)

        if len(candidates) > 1:
            return self._build_ambiguous_symbol_response(symbol_name, candidates)

        resolved_symbol = candidates[0].qualified_name if candidates else symbol_name
        result = self.code_graph.impact_analysis(
            symbol=resolved_symbol,
            max_depth=max_depth,
        )

        return {
            "symbol": symbol_name,
            "resolved_symbol": resolved_symbol,
            "ambiguous": False,
            "targets": [
                format_graph_node(node, node_role="target")
                for node in result["targets"]
            ],
            "affected": [
                format_graph_node(node, node_role="affected")
                for node in result["affected"]
            ],
        }

    def count_symbols(self, symbol_type: str = "all") -> Dict[str, Any]:
        """Count the number of symbols (functions, classes, methods, or all) in the repository."""
        symbol_type = symbol_type.lower()
        counts = {"function": 0, "class": 0, "method": 0}
        nodes_by_type = {"function": [], "class": [], "method": []}

        for node in self.code_graph.nodes.values():
            if node.node_type in counts:
                counts[node.node_type] += 1
                nodes_by_type[node.node_type].append(node)

        total = sum(counts.values())

        if symbol_type in counts:
            count = counts[symbol_type]
            items = [
                format_graph_node(n, node_role=symbol_type)
                for n in nodes_by_type[symbol_type]
            ]
            return {
                "symbol_type": symbol_type,
                "count": count,
                "items": items,
            }

        return {
            "symbol_type": "all",
            "count": total,
            "counts_by_type": counts,
            "items": [
                format_graph_node(n, node_role=n.node_type)
                for type_nodes in nodes_by_type.values()
                for n in type_nodes
            ],
        }

    def count_files(self, file_type: str = "python") -> Dict[str, Any]:
        """Count and list files in the repository by type.

        Parameters
        ----------
        file_type:
            ``"python"`` for ``.py`` files only, ``"all"`` for all
            supported indexed file types.
        """
        if file_type == "python":
            extensions = PYTHON_EXTENSIONS
        else:
            extensions = PYTHON_EXTENSIONS | DOC_EXTENSIONS | JSON_EXTENSIONS | TEXT_EXTENSIONS

        files: list[Dict[str, Any]] = []

        file_info: Dict[str, Dict[str, Any]] = {}  # path -> {extension, max_end_line}

        for chunk in self.retriever.indexed_chunks:
            p, start, end, _code = self._get_chunk_meta(chunk)
            if not p:
                continue

            relative_path = str(p).replace("\\", "/")
            ext = Path(relative_path).suffix.lower()

            if ext not in extensions:
                continue

            if relative_path not in file_info:
                file_info[relative_path] = {
                    "extension": ext,
                    "max_end_line": end or start,
                }
            else:
                current_max = file_info[relative_path]["max_end_line"]
                candidate = end or start
                if candidate > current_max:
                    file_info[relative_path]["max_end_line"] = candidate

        files = [
            {
                "relative_path": path,
                "extension": info["extension"],
                "line_count": info["max_end_line"],
            }
            for path, info in sorted(file_info.items())
        ]

        # Group counts by extension
        ext_counts: Dict[str, int] = {}
        for f in files:
            ext = f["extension"]
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        return {
            "file_type": file_type,
            "count": len(files),
            "counts_by_extension": ext_counts,
            "files": files,
        }
