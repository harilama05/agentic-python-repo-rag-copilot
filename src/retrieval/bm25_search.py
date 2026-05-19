"""BM25 lexical search over in-memory indexed chunks.

This module provides a minimal wrapper around `rank_bm25` for full-repository
lexical retrieval. It is used as one of the candidate sources for RRF fusion.

Important: logic is kept behavior-compatible with the previous implementation in
`src.retriever`.
"""

import re
from typing import Any, Callable, List

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> List[str]:
    """Tokenize natural language and code identifiers.

    Splits snake_case and non-alphanumeric characters.
    """
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return [token.lower() for token in text.split() if token.strip()]


class BM25Searcher:
    """Full-repository BM25 search over a list of indexed chunks."""

    def __init__(
        self,
        *,
        indexed_chunks: list[Any],
        get_text: Callable[[Any], str],
        get_chunk_id: Callable[[Any], str],
    ):
        self.indexed_chunks = indexed_chunks
        self._get_text = get_text
        self._get_chunk_id = get_chunk_id

        self.documents = [self._get_text(chunk) for chunk in self.indexed_chunks]
        self.tokenized_documents = [_tokenize(document) for document in self.documents]

        if self.tokenized_documents:
            self.bm25 = BM25Okapi(self.tokenized_documents)
        else:
            self.bm25 = None

    def search(self, query: str, top_k: int) -> list[tuple[str, Any, float]]:
        """Search chunks using BM25 and return (chunk_id, chunk, score)."""
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
            chunk_id = self._get_chunk_id(chunk)

            if not chunk_id:
                continue

            results.append((chunk_id, chunk, score))

        return results
