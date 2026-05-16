"""
Retriever — the main entry point for the retrieval pipeline.

Wraps ``HybridSearch`` and provides a clean interface for the agent.
"""

from typing import List

from src.constants import DEFAULT_CANDIDATE_K, DEFAULT_TOP_K
from src.schemas import SearchResult
from src.retrieval.hybrid_search import HybridSearch
from src.retrieval.vector_search import VectorSearch
from src.retrieval.keyword_search import KeywordSearch
from src.retrieval.symbol_search import SymbolSearch
from src.storage.vector_store import VectorStore
from src.storage.keyword_store import KeywordStore
from src.storage.metadata_store import MetadataStore


class Retriever:
    """
    High-level retriever facade.

    Instantiate from stores, delegates to ``HybridSearch`` internally.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        keyword_store: KeywordStore,
        metadata_store: MetadataStore,
    ):
        self.vector_store = vector_store
        self.keyword_store = keyword_store
        self.metadata_store = metadata_store

        self._hybrid = HybridSearch(
            vector_search=VectorSearch(vector_store),
            keyword_search=KeywordSearch(keyword_store),
            symbol_search=SymbolSearch(metadata_store),
        )

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
    ) -> List[SearchResult]:
        """
        Hybrid search: vector + BM25 + symbol, fused via RRF.
        """
        return self._hybrid.search(
            query=query, top_k=top_k, candidate_k=candidate_k
        )

    def find_symbol(self, symbol_name: str) -> List[SearchResult]:
        """Direct symbol lookup via metadata store."""
        return SymbolSearch(self.metadata_store).search(symbol_name)
