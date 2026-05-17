from typing import Any, Dict, List, Protocol

from sentence_transformers import CrossEncoder

from src.settings import CROSS_ENCODER_MODEL


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        ...


class NoOpReranker:
    """
    Fast mode reranker.

    Does not change retrieval results.
    """

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        return results[:top_k]


class CrossEncoderReranker:
    """
    Accurate mode reranker.

    Uses a Cross-Encoder to score each (query, chunk) pair.
    This is slower than normal retrieval but can improve relevance.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or CROSS_ENCODER_MODEL
        self.model: CrossEncoder | None = None

    def _get_model(self) -> CrossEncoder:
        if self.model is None:
            self.model = CrossEncoder(self.model_name)

        return self.model

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        pairs = []

        for result in results:
            text = result.get("text") or ""
            pairs.append((query, text))

        model = self._get_model()
        scores = model.predict(pairs)

        reranked_results = []

        for result, score in zip(results, scores):
            updated_result = dict(result)
            updated_result["cross_encoder_score"] = float(score)
            reranked_results.append(updated_result)

        reranked_results.sort(
            key=lambda item: item["cross_encoder_score"],
            reverse=True,
        )

        return reranked_results[:top_k]