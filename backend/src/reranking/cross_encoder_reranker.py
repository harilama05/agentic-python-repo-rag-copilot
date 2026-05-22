"""Cross-Encoder reranker for Accurate mode.

This module is intentionally isolated so Accurate mode can use a Cross-Encoder
without mixing model code into retrieval.
"""

from typing import Any, Dict, List, Protocol

from sentence_transformers import CrossEncoder

from src.core.settings import CROSS_ENCODER_MODEL


class CrossEncoderReranker:
    """Accurate mode reranker using a Cross-Encoder.

    Scores each (query, chunk_text) pair and sorts by the predicted relevance.
    """

    def __init__(
        self,
        model_name: str | None = None,
        text_key: str = "text",
        batch_size: int = 32,
    ):
        self.model_name = model_name or CROSS_ENCODER_MODEL
        self.text_key = text_key
        self.batch_size = batch_size
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
            text = result.get(self.text_key) or ""
            pairs.append((query, text))

        model = self._get_model()
        scores = model.predict(pairs, batch_size=self.batch_size)

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
