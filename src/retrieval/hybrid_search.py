"""
Hybrid search — orchestrates vector, keyword, and symbol search,
then fuses results using Reciprocal Rank Fusion (RRF).
"""

from typing import List, Optional

from src.constants import DEFAULT_CANDIDATE_K, DEFAULT_TOP_K
from src.schemas import SearchResult
from src.retrieval.vector_search import VectorSearch
from src.retrieval.keyword_search import KeywordSearch
from src.retrieval.symbol_search import SymbolSearch
from src.retrieval.rrf import reciprocal_rank_fusion
from src.retrieval.query_transform import extract_symbol_candidate


class HybridSearch:
    """
    Multi-signal retriever:
    1. Dense vector search (semantic)
    2. BM25 keyword search (lexical)
    3. Symbol name search (metadata)

    Results are fused via RRF for a single ranked list.
    """

    def __init__(
        self,
        vector_search: VectorSearch,
        keyword_search: KeywordSearch,
        symbol_search: SymbolSearch,
    ):
        self.vector = vector_search
        self.keyword = keyword_search
        self.symbol = symbol_search

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
    ) -> List[SearchResult]:
        """
        Run all three search strategies, fuse with RRF, return top_k.
        """
        ranked_lists: List[List[SearchResult]] = []

        # 1. Vector search
        vector_results = self.vector.search(query=query, top_k=candidate_k)
        if vector_results:
            ranked_lists.append(vector_results)

        # 2. BM25 keyword search
        keyword_results = self.keyword.search(query=query, top_k=candidate_k)
        if keyword_results:
            ranked_lists.append(keyword_results)

        # 3. Symbol search (if query contains a likely symbol name)
        symbol_candidate = extract_symbol_candidate(query)
        if symbol_candidate:
            symbol_results = self.symbol.search(symbol_candidate)
            if symbol_results:
                ranked_lists.append(symbol_results)

        if not ranked_lists:
            return []

        return reciprocal_rank_fusion(ranked_lists, top_k=top_k)
