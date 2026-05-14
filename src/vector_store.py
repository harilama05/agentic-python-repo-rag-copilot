from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import chromadb

from src.chunker import CodeChunk
from src.embeddings import LocalEmbeddingModel


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    score: float


def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata values must be str/int/float/bool.
    Convert None values to empty strings.
    """
    sanitized = {}

    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)

    return sanitized


class CodeVectorStore:
    def __init__(
        self,
        persist_dir: str | Path,
        collection_name: str = "python_code_chunks",
        embedding_model: LocalEmbeddingModel | None = None,
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection_name = collection_name
        self.embedding_model = embedding_model or LocalEmbeddingModel()

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name
        )

    def reset_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name
        )

    def add_chunks(self, chunks: List[CodeChunk]) -> None:
        if not chunks:
            return

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [_sanitize_metadata(chunk.metadata) for chunk in chunks]

        embeddings = self.embedding_model.embed_texts(documents)

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        query_embedding = self.embedding_model.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        output: List[SearchResult] = []

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            # Chroma distance is lower = more similar.
            # Convert to a simple similarity-like score.
            score = 1.0 - float(distance)

            output.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=document,
                    metadata=metadata,
                    score=score,
                )
            )

        return output