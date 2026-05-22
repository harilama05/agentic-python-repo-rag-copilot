"""Reranker interfaces and fast-mode reranker.

A reranker takes the formatted retrieval results (dicts) and returns a re-ordered
list, optionally attaching extra scores.
"""

from typing import Any, Dict, List, Protocol


class Reranker(Protocol):
    """Protocol for rerankers used by CodebaseTools."""

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Return a reranked version of results."""
        ...


class NoOpReranker:
    """Fast mode reranker.

    Does not change retrieval results.
    """

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        return results[:top_k]
