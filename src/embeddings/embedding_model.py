"""
Local embedding model using ``sentence-transformers``.

Designed for CPU execution — uses ``all-MiniLM-L6-v2`` by default which
produces 384-dimensional normalised embeddings in ~20 ms per sentence on
a modern CPU.
"""

from typing import List

from sentence_transformers import SentenceTransformer

from src.config import settings


class EmbeddingModel:
    """
    Wrapper around a ``SentenceTransformer`` model.

    Normalises all embeddings to unit vectors so that cosine similarity
    equals dot product.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model_name
        self._model = SentenceTransformer(self.model_name)

    @property
    def dimension(self) -> int:
        """Embedding dimensionality."""
        return self._model.get_sentence_embedding_dimension()

    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 64,
        show_progress: bool = True,
    ) -> List[List[float]]:
        """Embed a list of texts and return a list of float vectors."""
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        embedding = self._model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()
