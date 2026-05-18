import re
from dataclasses import dataclass
from typing import Any, Dict, List

from rank_bm25 import BM25Okapi

from src.settings import (
    BM25_WEIGHT,
    DEFAULT_CANDIDATE_K,
    DEFAULT_TOP_K,
    KEYWORD_WEIGHT,
    SYMBOL_WEIGHT,
    VECTOR_WEIGHT,
)

from src.constants import (
    DOCUMENTATION_QUERY_TYPE,
    DOCUMENTATION_QUERY_BOOST,
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

    source_type = str(metadata.get("source_type") or "").lower()

    return (
        source_type in {"documentation", "doc", "markdown"}
        or relative_path.endswith((".md", ".markdown"))
        or "readme" in relative_path
        or "/docs/" in relative_path
        or "\\docs\\" in relative_path
    )

def _normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [0.0 for _ in scores]

    return [(score - min_score) / (max_score - min_score) for score in scores]


def _get_result_text(result: Dict[str, Any]) -> str:
    return (
        result.get("text")
        or result.get("content")
        or result.get("code")
        or ""
    )


def _get_result_score(result: Dict[str, Any]) -> float:
    return float(
        result.get("score")
        or result.get("vector_score")
        or 0.0
    )


def _get_result_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    metadata = result.get("metadata")

    if isinstance(metadata, dict):
        return dict(metadata)

    return {}


def _get_result_value(
    result: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    metadata = _get_result_metadata(result)

    for key in keys:
        value = result.get(key)

        if value is not None:
            return value

        value = metadata.get(key)

        if value is not None:
            return value

    return default


def _build_result_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build normalized metadata for downstream tools.

    Qdrant returns dict results. This function ensures metadata contains
    the common keys expected by tools/agent/source rendering.
    """
    metadata = _get_result_metadata(result)

    normalized_fields = {
        "chunk_id": _get_result_value(result, "chunk_id"),
        "source_type": _get_result_value(result, "source_type"),
        "relative_path": _get_result_value(result, "relative_path", "file_path"),
        "file_path": _get_result_value(result, "file_path", "relative_path"),
        "start_line": _get_result_value(result, "start_line", "line_start"),
        "end_line": _get_result_value(result, "end_line", "line_end"),
        "line_start": _get_result_value(result, "line_start", "start_line"),
        "line_end": _get_result_value(result, "line_end", "end_line"),
        "symbol_name": _get_result_value(result, "symbol_name", "name"),
        "qualified_name": _get_result_value(result, "qualified_name", "symbol"),
        "symbol": _get_result_value(result, "symbol", "qualified_name", "symbol_name"),
        "symbol_type": _get_result_value(result, "symbol_type"),
        "heading": _get_result_value(result, "heading", "title"),
    }

    for key, value in normalized_fields.items():
        if value is not None and metadata.get(key) is None:
            metadata[key] = value

    return metadata


class CodeRetriever:
    """
    Hybrid retriever:
    - vector search from Qdrant
    - BM25 lexical scoring
    - keyword overlap scoring
    - symbol-aware scoring

    The vector store is expected to return dict results.
    """

    def __init__(self, vector_store: Any):
        self.vector_store = vector_store

    def search_code(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        query_type: str | None = None,
    ) -> List[CodeSearchResult]:
        vector_results: List[Dict[str, Any]] = self.vector_store.search(
            query=query,
            top_k=candidate_k,
        )

        if not vector_results:
            return []

        documents = [_get_result_text(result) for result in vector_results]

        tokenized_documents = [_tokenize(document) for document in documents]
        tokenized_query = _tokenize(query)

        bm25 = BM25Okapi(tokenized_documents)
        raw_bm25_scores = bm25.get_scores(tokenized_query).tolist()
        normalized_bm25_scores = _normalize_scores(raw_bm25_scores)

        reranked: List[CodeSearchResult] = []

        for result, document, bm25_score in zip(
            vector_results,
            documents,
            normalized_bm25_scores,
        ):
            metadata = _build_result_metadata(result)

            vector_score = _get_result_score(result)
            keyword_score = _score_keyword_match(query, document)
            symbol_score = _score_symbol_match(query, metadata)

            documentation_boost = 0.0

            if query_type == DOCUMENTATION_QUERY_TYPE and _is_documentation_result(metadata):
                documentation_boost = DOCUMENTATION_QUERY_BOOST

            final_score = (
                VECTOR_WEIGHT * vector_score
                + BM25_WEIGHT * bm25_score
                + SYMBOL_WEIGHT * symbol_score
                + KEYWORD_WEIGHT * keyword_score
                + documentation_boost
            )

            chunk_id = (
                str(_get_result_value(result, "chunk_id", default=""))
                or str(_get_result_value(result, "id", default=""))
            )

            reranked.append(
                CodeSearchResult(
                    chunk_id=chunk_id,
                    text=document,
                    metadata=metadata,
                    vector_score=vector_score,
                    bm25_score=bm25_score,
                    keyword_score=keyword_score,
                    symbol_score=symbol_score,
                    final_score=final_score,
                )
            )

        reranked.sort(key=lambda item: item.final_score, reverse=True)

        return reranked[:top_k]