"""
Vector search — thin wrapper for semantic search via the vector store.
"""

from typing import Any, Dict, List, Optional

from src.schemas import SearchResult
from src.storage.vector_store import VectorStore


class VectorSearch:
    """Semantic search using dense embeddings."""

    def __init__(self, vector_store: VectorStore):
        self._store = vector_store

    def search(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        return self._store.search(query=query, top_k=top_k, where=where)
