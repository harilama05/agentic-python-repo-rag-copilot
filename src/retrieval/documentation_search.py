"""Documentation-focused search for documentation queries.

This module identifies documentation chunks (README/docs markdown) and scores
query overlap against both content and lightweight metadata (heading/path).
Used as an additional candidate source for RRF when the router emits a
`documentation_query`.
"""

import re
from typing import Any, Callable, Dict, List


def _tokenize(text: str) -> List[str]:
    """Tokenize natural language and code identifiers."""
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


def is_documentation_result(metadata: Dict[str, Any]) -> bool:
    """Return True if the metadata represents a documentation chunk."""
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


def documentation_search(
    *,
    indexed_chunks: list[Any],
    query: str,
    top_k: int,
    build_metadata: Callable[[Any], Dict[str, Any]],
    get_chunk_id: Callable[[Any], str],
    get_text: Callable[[Any], str],
) -> list[tuple[str, Any, float]]:
    """Search documentation-like chunks and return (chunk_id, chunk, score)."""
    scored: list[tuple[str, Any, float]] = []

    for chunk in indexed_chunks:
        metadata = build_metadata(chunk)

        if not is_documentation_result(metadata):
            continue

        text = get_text(chunk)
        heading = str(metadata.get("heading") or "")
        relative_path = str(metadata.get("relative_path") or "")
        doc_meta_text = f"{heading} {relative_path}"

        keyword_score = _score_keyword_match(query, text)
        metadata_score = _score_keyword_match(query, doc_meta_text)
        score = keyword_score + metadata_score + 0.25

        chunk_id = get_chunk_id(chunk)

        if not chunk_id:
            continue

        scored.append((chunk_id, chunk, score))

    scored.sort(key=lambda item: item[2], reverse=True)

    return scored[:top_k]
