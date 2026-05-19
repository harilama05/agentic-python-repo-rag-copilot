"""Hybrid retrieval for indexed Python repositories.

This module implements the core hybrid retrieval pipeline used by the app.
It performs multi-source candidate retrieval and fuses ranked lists using
Reciprocal Rank Fusion (RRF).

Behavior is intentionally kept compatible with the previous implementation in
`src.retriever`.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from src.core.constants import DOCUMENTATION_QUERY_TYPE
from src.core.settings import (
    DEFAULT_CANDIDATE_K,
    DEFAULT_TOP_K,
    RRF_BM25_CANDIDATE_K,
    RRF_DOCUMENTATION_CANDIDATE_K,
    RRF_K,
    RRF_SYMBOL_CANDIDATE_K,
    RRF_VECTOR_CANDIDATE_K,
)

from src.retrieval.bm25_search import BM25Searcher
from src.retrieval.documentation_search import documentation_search
from src.retrieval.rrf import rrf_fuse
from src.retrieval.symbol_search import symbol_search


@dataclass
class CodeSearchResult:
    """Normalized retrieval result returned by CodeRetriever.

    The app formats this into a dict schema in `src.tools.format_search_result`.
    """

    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float
    bm25_score: float
    keyword_score: float
    symbol_score: float
    final_score: float


def _get_item_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(
            item.get("text")
            or item.get("content")
            or item.get("code")
            or ""
        )

    return str(
        getattr(item, "text", None)
        or getattr(item, "content", None)
        or getattr(item, "code", None)
        or ""
    )


def _get_raw_metadata(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        metadata = item.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}

    metadata = getattr(item, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _get_item_value(
    item: Any,
    *keys: str,
    default: Any = None,
) -> Any:
    metadata = _get_raw_metadata(item)

    if isinstance(item, dict):
        for key in keys:
            value = item.get(key)

            if value is not None:
                return value

            value = metadata.get(key)

            if value is not None:
                return value

        return default

    for key in keys:
        value = getattr(item, key, None)

        if value is not None:
            return value

        value = metadata.get(key)

        if value is not None:
            return value

    return default


def _build_item_metadata(item: Any) -> Dict[str, Any]:
    """Build normalized metadata for downstream tools.

    Supports:
    - Qdrant dict results
    - CodeChunk dataclass objects
    - DB-loaded chunk dicts
    """
    metadata = _get_raw_metadata(item)

    normalized_fields = {
        "chunk_id": _get_item_value(item, "chunk_id"),
        "source_type": _get_item_value(item, "source_type"),
        "relative_path": _get_item_value(item, "relative_path", "file_path"),
        "file_path": _get_item_value(item, "file_path", "relative_path"),
        "start_line": _get_item_value(item, "start_line", "line_start"),
        "end_line": _get_item_value(item, "end_line", "line_end"),
        "line_start": _get_item_value(item, "line_start", "start_line"),
        "line_end": _get_item_value(item, "line_end", "end_line"),
        "symbol_name": _get_item_value(item, "symbol_name", "name"),
        "qualified_name": _get_item_value(item, "qualified_name", "symbol"),
        "symbol": _get_item_value(item, "symbol", "qualified_name", "symbol_name"),
        "symbol_type": _get_item_value(item, "symbol_type"),
        "heading": _get_item_value(item, "heading", "title"),
    }

    for key, value in normalized_fields.items():
        if value is not None and metadata.get(key) is None:
            metadata[key] = value

    return metadata


def _get_item_chunk_id(item: Any) -> str:
    value = _get_item_value(item, "chunk_id", "id", default="")
    return str(value or "")


def _get_item_score(item: Any) -> float:
    value = _get_item_value(item, "score", "vector_score", default=0.0)

    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


class CodeRetriever:
    """RRF retriever.

    Candidate sources:
    - Qdrant vector search
    - full-repository BM25 search over indexed chunks
    - symbol metadata search
    - documentation search for documentation queries

    RRF fuses ranked lists using ranks, not raw score scales.
    """

    def __init__(
        self,
        vector_store: Any,
        indexed_chunks: list[Any] | None = None,
    ):
        self.vector_store = vector_store
        self.indexed_chunks = indexed_chunks or []

        self.chunk_by_id: Dict[str, Any] = {}

        for chunk in self.indexed_chunks:
            chunk_id = _get_item_chunk_id(chunk)

            if chunk_id:
                self.chunk_by_id[chunk_id] = chunk

        self.bm25_searcher = BM25Searcher(
            indexed_chunks=self.indexed_chunks,
            get_text=_get_item_text,
            get_chunk_id=_get_item_chunk_id,
        )

    def _vector_search(self, query: str, top_k: int) -> list[tuple[str, Any, float]]:
        results = self.vector_store.search(
            query=query,
            top_k=top_k,
        )

        output: list[tuple[str, Any, float]] = []

        for result in results:
            chunk_id = _get_item_chunk_id(result)

            if not chunk_id:
                continue

            output.append((chunk_id, result, _get_item_score(result)))

        return output

    def search_code(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        query_type: str | None = None,
    ) -> List[CodeSearchResult]:
        """Search indexed repository chunks using multi-source retrieval + RRF."""
        vector_k = max(RRF_VECTOR_CANDIDATE_K, candidate_k, top_k)
        bm25_k = max(RRF_BM25_CANDIDATE_K, candidate_k, top_k)
        symbol_k = max(RRF_SYMBOL_CANDIDATE_K, top_k)

        vector_results = self._vector_search(query, top_k=vector_k)
        bm25_results = self.bm25_searcher.search(query, top_k=bm25_k)
        symbol_results = symbol_search(
            indexed_chunks=self.indexed_chunks,
            query=query,
            top_k=symbol_k,
            build_metadata=_build_item_metadata,
            get_chunk_id=_get_item_chunk_id,
        )

        documentation_results: list[tuple[str, Any, float]] = []
        if query_type == DOCUMENTATION_QUERY_TYPE:
            documentation_results = documentation_search(
                indexed_chunks=self.indexed_chunks,
                query=query,
                top_k=max(RRF_DOCUMENTATION_CANDIDATE_K, top_k),
                build_metadata=_build_item_metadata,
                get_chunk_id=_get_item_chunk_id,
                get_text=_get_item_text,
            )

        ranked_lists = [
            [chunk_id for chunk_id, _, _ in vector_results],
            [chunk_id for chunk_id, _, _ in bm25_results],
            [chunk_id for chunk_id, _, _ in symbol_results],
        ]

        if documentation_results:
            ranked_lists.append([chunk_id for chunk_id, _, _ in documentation_results])

        rrf_scores = rrf_fuse(
            ranked_lists=ranked_lists,
            rrf_k=RRF_K,
        )

        candidates: Dict[str, Any] = {}

        vector_scores: Dict[str, float] = {}
        bm25_scores: Dict[str, float] = {}
        symbol_scores: Dict[str, float] = {}
        documentation_scores: Dict[str, float] = {}

        for chunk_id, item, score in vector_results:
            candidates.setdefault(chunk_id, item)
            vector_scores[chunk_id] = score

        for chunk_id, item, score in bm25_results:
            candidates.setdefault(chunk_id, item)
            bm25_scores[chunk_id] = score

        for chunk_id, item, score in symbol_results:
            candidates.setdefault(chunk_id, item)
            symbol_scores[chunk_id] = score

        for chunk_id, item, score in documentation_results:
            candidates.setdefault(chunk_id, item)
            documentation_scores[chunk_id] = score

        reranked: List[CodeSearchResult] = []

        for chunk_id, rrf_score in rrf_scores.items():
            item = candidates.get(chunk_id) or self.chunk_by_id.get(chunk_id)

            if item is None:
                continue

            text = _get_item_text(item)
            metadata = _build_item_metadata(item)
            metadata["rrf_score"] = rrf_score

            rrf_sources = []
            if chunk_id in vector_scores:
                rrf_sources.append("vector")
            if chunk_id in bm25_scores:
                rrf_sources.append("bm25")
            if chunk_id in symbol_scores:
                rrf_sources.append("symbol")
            if chunk_id in documentation_scores:
                rrf_sources.append("documentation")

            metadata["rrf_sources"] = rrf_sources

            reranked.append(
                CodeSearchResult(
                    chunk_id=chunk_id,
                    text=text,
                    metadata=metadata,
                    vector_score=vector_scores.get(chunk_id, 0.0),
                    bm25_score=bm25_scores.get(chunk_id, 0.0),
                    keyword_score=documentation_scores.get(chunk_id, 0.0),
                    symbol_score=symbol_scores.get(chunk_id, 0.0),
                    final_score=rrf_score,
                )
            )

        reranked.sort(key=lambda item: item.final_score, reverse=True)

        return reranked[:top_k]
