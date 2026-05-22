"""Symbol metadata search for hybrid retrieval.

This is a lightweight lexical scorer that matches a query against chunk metadata
(symbol_name, qualified_name, symbol_type). It is used as an additional candidate
source for RRF.
"""

import re
from typing import Any, Callable, Dict, List


def _tokenize(text: str) -> List[str]:
    """Tokenize natural language and code identifiers."""
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return [token.lower() for token in text.split() if token.strip()]


def score_symbol_match(query: str, metadata: Dict[str, Any]) -> float:
    """Score how well a query matches symbol-related metadata."""
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


def symbol_search(
    *,
    indexed_chunks: list[Any],
    query: str,
    top_k: int,
    build_metadata: Callable[[Any], Dict[str, Any]],
    get_chunk_id: Callable[[Any], str],
) -> list[tuple[str, Any, float]]:
    """Search chunks by symbol metadata and return (chunk_id, chunk, score)."""
    scored: list[tuple[str, Any, float]] = []

    for chunk in indexed_chunks:
        metadata = build_metadata(chunk)
        score = score_symbol_match(query, metadata)

        if score <= 0:
            continue

        chunk_id = get_chunk_id(chunk)

        if not chunk_id:
            continue

        scored.append((chunk_id, chunk, score))

    scored.sort(key=lambda item: item[2], reverse=True)

    return scored[:top_k]
