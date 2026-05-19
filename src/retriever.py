import re
from dataclasses import dataclass
from typing import Any, Dict, List

from rank_bm25 import BM25Okapi

from src.constants import (
    DOCUMENTATION_QUERY_TYPE,
)
from src.settings import (
    DEFAULT_CANDIDATE_K,
    DEFAULT_TOP_K,
    RRF_BM25_CANDIDATE_K,
    RRF_DOCUMENTATION_CANDIDATE_K,
    RRF_K,
    RRF_SYMBOL_CANDIDATE_K,
    RRF_VECTOR_CANDIDATE_K,
)


@dataclass
class CodeSearchResult:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float
    bm25_score: float
    keyword_score: float
    symbol_score: float
    final_score: float


def _tokenize(text: str) -> List[str]:
    """
    Simple tokenizer for natural language and code identifiers.
    Splits snake_case and non-alphanumeric characters.
    """
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return [token.lower() for token in text.split() if token.strip()]


def _score_keyword_match(query: str, document: str) -> float:
    query_tokens = set(_tokenize(query))
    document_tokens = set(_tokenize(document))

    if not query_tokens:
        return 0.0

    overlap = query_tokens.intersection(document_tokens)
    return len(overlap) / len(query_tokens)


def _score_symbol_match(query: str, metadata: Dict[str, Any]) -> float:
    query_tokens = set(_tokenize(query))

    symbol_name = str(metadata.get("symbol_name") or "")
    qualified_name = str(metadata.get("qualified_name") or "")
    symbol_type = str(metadata.get("symbol_type") or "")

    symbol_text = f"{symbol_name} {qualified_name} {symbol_type}"
    symbol_tokens = set(_tokenize(symbol_text))

    if not query_tokens:
        return 0.0

    overlap = query_tokens.intersection(symbol_tokens)
    score = len(overlap) / len(query_tokens)

    if "function" in query_tokens and symbol_type in {"function", "async_function"}:
        score += 0.25

    if "class" in query_tokens and symbol_type == "class":
        score += 0.25

    if "method" in query_tokens and symbol_type in {"method", "async_method"}:
        score += 0.25

    return min(score, 1.0)


def _is_documentation_result(metadata: Dict[str, Any]) -> bool:
    relative_path = str(
        metadata.get("relative_path")
        or metadata.get("file_path")
        or ""
    ).lower()

    normalized_path = relative_path.replace("\\", "/")
    source_type = str(metadata.get("source_type") or "").lower()

    return (
        source_type in {"documentation", "doc", "markdown"}
        or normalized_path.endswith((".md", ".markdown"))
        or "readme" in normalized_path
        or "/docs/" in normalized_path
    )


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
    """
    Build normalized metadata for downstream tools.

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


def _rrf_fuse(
    ranked_lists: list[list[str]],
    rrf_k: int,
) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            if not chunk_id:
                continue

            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)

    return scores


class CodeRetriever:
    """
    RRF retriever.

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

        self.documents = [_get_item_text(chunk) for chunk in self.indexed_chunks]
        self.tokenized_documents = [_tokenize(document) for document in self.documents]

        if self.tokenized_documents:
            self.bm25 = BM25Okapi(self.tokenized_documents)
        else:
            self.bm25 = None

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

    def _bm25_search(self, query: str, top_k: int) -> list[tuple[str, Any, float]]:
        if self.bm25 is None or not self.indexed_chunks:
            return []

        tokenized_query = _tokenize(query)

        if not tokenized_query:
            return []

        raw_scores = self.bm25.get_scores(tokenized_query).tolist()

        ranked_indices = sorted(
            range(len(raw_scores)),
            key=lambda index: raw_scores[index],
            reverse=True,
        )

        results: list[tuple[str, Any, float]] = []

        for index in ranked_indices[:top_k]:
            score = float(raw_scores[index])

            if score <= 0:
                continue

            chunk = self.indexed_chunks[index]
            chunk_id = _get_item_chunk_id(chunk)

            if not chunk_id:
                continue

            results.append((chunk_id, chunk, score))

        return results

    def _symbol_search(self, query: str, top_k: int) -> list[tuple[str, Any, float]]:
        scored: list[tuple[str, Any, float]] = []

        for chunk in self.indexed_chunks:
            metadata = _build_item_metadata(chunk)
            score = _score_symbol_match(query, metadata)

            if score <= 0:
                continue

            chunk_id = _get_item_chunk_id(chunk)

            if not chunk_id:
                continue

            scored.append((chunk_id, chunk, score))

        scored.sort(key=lambda item: item[2], reverse=True)

        return scored[:top_k]

    def _documentation_search(self, query: str, top_k: int) -> list[tuple[str, Any, float]]:
        scored: list[tuple[str, Any, float]] = []

        for chunk in self.indexed_chunks:
            metadata = _build_item_metadata(chunk)

            if not _is_documentation_result(metadata):
                continue

            text = _get_item_text(chunk)
            heading = str(metadata.get("heading") or "")
            relative_path = str(metadata.get("relative_path") or "")
            doc_meta_text = f"{heading} {relative_path}"

            keyword_score = _score_keyword_match(query, text)
            metadata_score = _score_keyword_match(query, doc_meta_text)
            score = keyword_score + metadata_score + 0.25

            chunk_id = _get_item_chunk_id(chunk)

            if not chunk_id:
                continue

            scored.append((chunk_id, chunk, score))

        scored.sort(key=lambda item: item[2], reverse=True)

        return scored[:top_k]

    def search_code(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        query_type: str | None = None,
    ) -> List[CodeSearchResult]:
        vector_k = max(RRF_VECTOR_CANDIDATE_K, candidate_k, top_k)
        bm25_k = max(RRF_BM25_CANDIDATE_K, candidate_k, top_k)
        symbol_k = max(RRF_SYMBOL_CANDIDATE_K, top_k)

        vector_results = self._vector_search(query, top_k=vector_k)
        bm25_results = self._bm25_search(query, top_k=bm25_k)
        symbol_results = self._symbol_search(query, top_k=symbol_k)

        documentation_results: list[tuple[str, Any, float]] = []
        if query_type == DOCUMENTATION_QUERY_TYPE:
            documentation_results = self._documentation_search(
                query=query,
                top_k=max(RRF_DOCUMENTATION_CANDIDATE_K, top_k),
            )

        ranked_lists = [
            [chunk_id for chunk_id, _, _ in vector_results],
            [chunk_id for chunk_id, _, _ in bm25_results],
            [chunk_id for chunk_id, _, _ in symbol_results],
        ]

        if documentation_results:
            ranked_lists.append([chunk_id for chunk_id, _, _ in documentation_results])

        rrf_scores = _rrf_fuse(
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
