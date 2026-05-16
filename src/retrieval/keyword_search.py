"""
Keyword search — thin wrapper for BM25 search via the keyword store.
"""

from typing import List

from src.schemas import SearchResult
from src.storage.keyword_store import KeywordStore


class KeywordSearch:
    """Lexical search using BM25Okapi."""

    def __init__(self, keyword_store: KeywordStore):
        self._store = keyword_store

    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        return self._store.search(query=query, top_k=top_k)
