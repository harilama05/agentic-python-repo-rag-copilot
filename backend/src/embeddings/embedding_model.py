"""Embedding model wrapper used for code and documentation chunks."""

from typing import List

from sentence_transformers import SentenceTransformer

from src.core.settings import DEFAULT_EMBEDDING_MODEL


class LocalEmbeddingModel:
    """Local CPU embedding model using sentence-transformers."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or DEFAULT_EMBEDDING_MODEL
        self.model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts into normalized dense vectors."""
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed one query string into a normalized dense vector."""
        embedding = self.model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embedding.tolist()
