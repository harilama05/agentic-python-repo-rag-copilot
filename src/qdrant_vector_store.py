import hashlib
import uuid
from typing import Any, Iterable

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from src.embeddings import LocalEmbeddingModel
from src.settings import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL


def make_stable_chunk_id(
    repo_id: str,
    relative_path: str,
    start_line: int | None,
    end_line: int | None,
    text: str,
) -> str:
    raw = f"{repo_id}:{relative_path}:{start_line}:{end_line}:{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_qdrant_point_id(chunk_id: str) -> str:
    """
    Qdrant point id can be UUID string.
    Convert stable chunk id into deterministic UUID.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def get_chunk_text(chunk: Any) -> str:
    return (
        getattr(chunk, "text", None)
        or getattr(chunk, "content", None)
        or getattr(chunk, "code", None)
        or ""
    )


def get_chunk_metadata(chunk: Any) -> dict[str, Any]:
    metadata = getattr(chunk, "metadata", None)

    if isinstance(metadata, dict):
        return metadata

    return {}


def get_metadata_value(
    metadata: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    for key in keys:
        value = metadata.get(key)

        if value is not None:
            return value

    return default


class QdrantCodeVectorStore:
    """
    Qdrant-backed vector store for code/document chunks.

    One global collection is used for all repositories.
    Each point is filtered by repo_id.
    """

    def __init__(
        self,
        repo_id: str,
        collection_name: str = QDRANT_COLLECTION,
        url: str = QDRANT_URL,
        api_key: str | None = QDRANT_API_KEY,
    ):
        self.repo_id = repo_id
        self.collection_name = collection_name
        self.client = QdrantClient(url=url, api_key=api_key)
        self.embedding_model = LocalEmbeddingModel()

    def _collection_exists(self) -> bool:
        collections = self.client.get_collections().collections
        return any(collection.name == self.collection_name for collection in collections)

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_exists():
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    def reset_collection(self) -> None:
        """
        Backward-compatible name.

        In product mode, we do not drop the whole collection because it may contain
        vectors from many repos. We delete only points for the current repo_id.
        """
        if not self._collection_exists():
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="repo_id",
                        match=MatchValue(value=self.repo_id),
                    )
                ]
            ),
        )

    def add_chunks(self, chunks: Iterable[Any], batch_size: int = 64) -> None:
        chunks = list(chunks)

        if not chunks:
            return

        texts = [get_chunk_text(chunk) for chunk in chunks]
        embeddings = self.embedding_model.embed_texts(texts)

        if not embeddings:
            return

        self._ensure_collection(vector_size=len(embeddings[0]))

        points: list[PointStruct] = []

        for chunk, text, embedding in zip(chunks, texts, embeddings):
            metadata = get_chunk_metadata(chunk)

            relative_path = get_metadata_value(
                metadata,
                "relative_path",
                "file_path",
                "path",
                default="",
            )

            start_line = get_metadata_value(
                metadata,
                "start_line",
                "line_start",
            )

            end_line = get_metadata_value(
                metadata,
                "end_line",
                "line_end",
            )

            chunk_id = (
                getattr(chunk, "chunk_id", None)
                or metadata.get("chunk_id")
                or make_stable_chunk_id(
                    repo_id=self.repo_id,
                    relative_path=str(relative_path),
                    start_line=start_line,
                    end_line=end_line,
                    text=text,
                )
            )

            source_type = get_metadata_value(
                metadata,
                "source_type",
                "type",
            )

            symbol_name = get_metadata_value(
                metadata,
                "symbol_name",
                "name",
            )

            qualified_name = get_metadata_value(
                metadata,
                "qualified_name",
                "symbol",
            )

            symbol_type = get_metadata_value(
                metadata,
                "symbol_type",
                "type",
            )

            heading = get_metadata_value(
                metadata,
                "heading",
                "title",
            )

            payload = {
                "repo_id": self.repo_id,
                "chunk_id": str(chunk_id),
                "text": text,
                "source_type": source_type,
                "relative_path": str(relative_path),
                "start_line": start_line,
                "end_line": end_line,
                "symbol_name": symbol_name,
                "qualified_name": qualified_name,
                "symbol_type": symbol_type,
                "heading": heading,
            }

            points.append(
                PointStruct(
                    id=make_qdrant_point_id(str(chunk_id)),
                    vector=embedding,
                    payload=payload,
                )
            )

        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]

            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

    def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._collection_exists():
            return []

        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="repo_id",
                        match=MatchValue(value=self.repo_id),
                    )
                ]
            ),
            limit=top_k,
            with_payload=True,
        )

        results: list[dict[str, Any]] = []

        for hit in hits:
            payload = hit.payload or {}

            result = {
                "id": str(hit.id),
                "score": hit.score,
                "text": payload.get("text", ""),
                "chunk_id": payload.get("chunk_id"),
                "source_type": payload.get("source_type"),
                "relative_path": payload.get("relative_path"),
                "start_line": payload.get("start_line"),
                "end_line": payload.get("end_line"),
                "symbol_name": payload.get("symbol_name"),
                "qualified_name": payload.get("qualified_name"),
                "symbol_type": payload.get("symbol_type"),
                "heading": payload.get("heading"),
                "metadata": payload,
            }

            results.append(result)

        return results

    def search(
        self,
        query_embedding: list[float] | None = None,
        top_k: int = 10,
        query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Compatibility method.

        Supports:
        - search(query_embedding=[...], top_k=10)
        - search(query_text="...", top_k=10)
        """
        if query_embedding is None:
            if not query_text:
                raise ValueError("Either query_embedding or query_text must be provided")

            query_embedding = self.embedding_model.embed_query(query_text)

        return self.search_by_vector(
            query_embedding=query_embedding,
            top_k=top_k,
        )

    def search_text(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        query_embedding = self.embedding_model.embed_query(query)

        return self.search_by_vector(
            query_embedding=query_embedding,
            top_k=top_k,
        )