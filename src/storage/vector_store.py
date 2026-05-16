"""
ChromaDB-based vector store.

Stores code/text chunks as dense vectors for semantic search.  Uses
cosine similarity (``hnsw:space = cosine``) so that
``score = 1 - distance`` always lies in ``[0, 1]``.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from src.config import settings
from src.embeddings.embedding_model import EmbeddingModel
from src.metadata.metadata_builder import sanitize_metadata
from src.schemas import Chunk, SearchResult


class VectorStore:
    """
    Thin wrapper around a ChromaDB persistent collection.
    """

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        collection_name: str | None = None,
        embedding_model: EmbeddingModel | None = None,
    ):
        self.persist_dir = Path(persist_dir or settings.chroma_persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection_name = collection_name or settings.chroma_collection_name
        self.embedding_model = embedding_model or EmbeddingModel()

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine distance ∈ [0,1]
        )

    def reset(self) -> None:
        """Delete and recreate the collection."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """Embed and store a batch of chunks."""
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [sanitize_metadata(c.metadata) for c in chunks]
        embeddings = self.embedding_model.embed_texts(documents)

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Semantic search using cosine similarity.

        Returns results sorted by descending similarity score.
        """
        query_embedding = self.embedding_model.embed_query(query)

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        output: List[SearchResult] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            score = 1.0 - float(dist)  # cosine distance → similarity
            output.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=doc,
                    metadata=meta,
                    score=score,
                )
            )

        return output

    @property
    def count(self) -> int:
        return self.collection.count()
