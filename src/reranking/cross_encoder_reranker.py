"""
Cross-encoder reranker — uses a cross-encoder model to score
(query, document) pairs for high-precision reranking.

Cross-encoders are ~10x more accurate than bi-encoders for relevance
scoring because they attend jointly to query and document.
"""

from typing import List, Tuple

from sentence_transformers import CrossEncoder

from src.config import settings
from src.schemas import SearchResult


class CrossEncoderReranker:
    """
    Reranks search results using a cross-encoder model.

    Default model: ``cross-encoder/ms-marco-MiniLM-L-6-v2``
    (fast on CPU, good accuracy).
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.cross_encoder_model_name
        self._model = CrossEncoder(self.model_name)

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 5,
    ) -> List[SearchResult]:
        """
        Score each result against the query using the cross-encoder,
        then return top_k sorted by cross-encoder score.
        """
        if not results:
            return []

        # Build (query, document) pairs
        pairs: List[Tuple[str, str]] = [
            (query, result.text) for result in results
        ]

        # Score
        scores = self._model.predict(pairs)

        # Attach scores and sort
        scored: List[Tuple[float, SearchResult]] = []
        for score, result in zip(scores, results):
            reranked = SearchResult(
                chunk_id=result.chunk_id,
                text=result.text,
                content=result.content,
                metadata=result.metadata,
                score=float(score),
            )
            scored.append((float(score), reranked))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [r for _, r in scored[:top_k]]
