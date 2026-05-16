"""
Reranker — orchestrates cross-encoder reranking and optional MMR
diversity filtering.
"""

from typing import List

from src.schemas import SearchResult
from src.reranking.cross_encoder_reranker import CrossEncoderReranker
from src.reranking.mmr import mmr_rerank
from src.embeddings.embedding_model import EmbeddingModel
from src.constants import DEFAULT_RERANK_TOP_K


class Reranker:
    """
    Two-stage reranker:
    1. **Cross-encoder** scores each (query, doc) pair for relevance.
    2. **MMR** (optional) diversifies the top results.
    """

    def __init__(
        self,
        cross_encoder: CrossEncoderReranker | None = None,
        embedding_model: EmbeddingModel | None = None,
        use_mmr: bool = False,
        mmr_lambda: float = 0.7,
    ):
        self._cross_encoder = cross_encoder or CrossEncoderReranker()
        self._embedding_model = embedding_model
        self._use_mmr = use_mmr
        self._mmr_lambda = mmr_lambda

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = DEFAULT_RERANK_TOP_K,
    ) -> List[SearchResult]:
        """
        Rerank results: cross-encoder first, then optionally MMR.
        """
        if not results:
            return []

        # Stage 1: Cross-encoder reranking
        reranked = self._cross_encoder.rerank(
            query=query,
            results=results,
            top_k=top_k * 2 if self._use_mmr else top_k,
        )

        # Stage 2: MMR diversity (optional)
        if self._use_mmr and self._embedding_model and len(reranked) > 1:
            reranked = mmr_rerank(
                query=query,
                results=reranked,
                embedding_model=self._embedding_model,
                top_k=top_k,
                lambda_param=self._mmr_lambda,
            )

        return reranked[:top_k]
