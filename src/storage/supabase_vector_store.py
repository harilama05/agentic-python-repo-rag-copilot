"""Supabase/Postgres pgvector-backed vector store implementation."""

import hashlib
import uuid
from typing import Any, Iterable

from sqlalchemy import text

from src.core.settings import EMBEDDING_DIMENSION
from src.db.session import get_db_session
from src.embeddings.embedding_model import LocalEmbeddingModel


def sanitize_postgres_text(value: Any) -> Any:
    """Remove NUL bytes because PostgreSQL TEXT/VARCHAR fields cannot store them."""
    if isinstance(value, str):
        return value.replace("\x00", "")

    return value


def sanitize_postgres_text_or_empty(value: Any) -> str:
    """Return a NUL-free string, using an empty string for None."""
    if value is None:
        return ""

    return str(value).replace("\x00", "")


def make_stable_chunk_id(
    repo_id: str,
    relative_path: str,
    start_line: int | None,
    end_line: int | None,
    chunk_text: str,
) -> str:
    chunk_text = sanitize_postgres_text_or_empty(chunk_text)
    relative_path = sanitize_postgres_text_or_empty(relative_path)
    raw = f"{repo_id}:{relative_path}:{start_line}:{end_line}:{chunk_text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def get_chunk_text(chunk: Any) -> str:
    text = (
        getattr(chunk, "text", None)
        or getattr(chunk, "content", None)
        or getattr(chunk, "code", None)
        or ""
    )

    return sanitize_postgres_text_or_empty(text)


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


def format_vector(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


class SupabaseCodeVectorStore:
    """Supabase/Postgres pgvector store for code and documentation chunks."""

    def __init__(
        self,
        repo_id: str,
        embedding_dimension: int = EMBEDDING_DIMENSION,
    ):
        self.repo_id = repo_id
        self.embedding_dimension = embedding_dimension
        self.embedding_model = LocalEmbeddingModel()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with get_db_session() as session:
            session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS chunk_embeddings (
                        chunk_id varchar(255) PRIMARY KEY,
                        repo_id varchar(255) NOT NULL,
                        point_id uuid NOT NULL,
                        text text NOT NULL,
                        source_type varchar(50),
                        relative_path text NOT NULL,
                        start_line integer,
                        end_line integer,
                        symbol_name varchar(255),
                        qualified_name varchar(500),
                        symbol_type varchar(100),
                        heading text,
                        embedding vector({self.embedding_dimension}) NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo_id "
                    "ON chunk_embeddings (repo_id)"
                )
            )
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo_path "
                    "ON chunk_embeddings (repo_id, relative_path)"
                )
            )
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo_symbol "
                    "ON chunk_embeddings (repo_id, qualified_name)"
                )
            )

    def reset_collection(self) -> None:
        """Delete only vectors for the current repo_id from Supabase/Postgres."""
        with get_db_session() as session:
            session.execute(
                text("DELETE FROM chunk_embeddings WHERE repo_id = :repo_id"),
                {"repo_id": sanitize_postgres_text_or_empty(self.repo_id)},
            )

    def add_chunks(self, chunks: Iterable[Any], batch_size: int = 64) -> None:
        """Embed and upsert chunks into Supabase/Postgres pgvector."""
        chunks = list(chunks)

        if not chunks:
            return

        texts = [get_chunk_text(chunk) for chunk in chunks]
        embeddings = self.embedding_model.embed_texts(texts)

        if not embeddings:
            return

        rows: list[dict[str, Any]] = []

        for chunk, chunk_text, embedding in zip(chunks, texts, embeddings):
            metadata = get_chunk_metadata(chunk)

            relative_path = get_metadata_value(
                metadata,
                "relative_path",
                "file_path",
                "path",
                default="",
            )
            relative_path = sanitize_postgres_text_or_empty(relative_path)

            start_line = get_metadata_value(metadata, "start_line", "line_start")
            end_line = get_metadata_value(metadata, "end_line", "line_end")
            chunk_id = (
                getattr(chunk, "chunk_id", None)
                or metadata.get("chunk_id")
                or make_stable_chunk_id(
                    repo_id=self.repo_id,
                    relative_path=relative_path,
                    start_line=start_line,
                    end_line=end_line,
                    chunk_text=chunk_text,
                )
            )
            chunk_id = sanitize_postgres_text_or_empty(chunk_id)

            rows.append(
                {
                    "chunk_id": chunk_id,
                    "repo_id": sanitize_postgres_text_or_empty(self.repo_id),
                    "point_id": make_point_id(chunk_id),
                    "text": chunk_text,
                    "source_type": sanitize_postgres_text(
                        get_metadata_value(metadata, "source_type", "type")
                    ),
                    "relative_path": relative_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "symbol_name": sanitize_postgres_text(
                        get_metadata_value(metadata, "symbol_name", "name")
                    ),
                    "qualified_name": sanitize_postgres_text(
                        get_metadata_value(
                            metadata,
                            "qualified_name",
                            "symbol",
                        )
                    ),
                    "symbol_type": sanitize_postgres_text(
                        get_metadata_value(metadata, "symbol_type", "type")
                    ),
                    "heading": sanitize_postgres_text(
                        get_metadata_value(metadata, "heading", "title")
                    ),
                    "embedding": format_vector(embedding),
                }
            )

        stmt = text(
            """
            INSERT INTO chunk_embeddings (
                chunk_id,
                repo_id,
                point_id,
                text,
                source_type,
                relative_path,
                start_line,
                end_line,
                symbol_name,
                qualified_name,
                symbol_type,
                heading,
                embedding
            )
            VALUES (
                :chunk_id,
                :repo_id,
                :point_id,
                :text,
                :source_type,
                :relative_path,
                :start_line,
                :end_line,
                :symbol_name,
                :qualified_name,
                :symbol_type,
                :heading,
                CAST(:embedding AS vector)
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                repo_id = EXCLUDED.repo_id,
                point_id = EXCLUDED.point_id,
                text = EXCLUDED.text,
                source_type = EXCLUDED.source_type,
                relative_path = EXCLUDED.relative_path,
                start_line = EXCLUDED.start_line,
                end_line = EXCLUDED.end_line,
                symbol_name = EXCLUDED.symbol_name,
                qualified_name = EXCLUDED.qualified_name,
                symbol_type = EXCLUDED.symbol_type,
                heading = EXCLUDED.heading,
                embedding = EXCLUDED.embedding
            """
        )

        with get_db_session() as session:
            for start in range(0, len(rows), batch_size):
                session.execute(stmt, rows[start : start + batch_size])

    def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search chunks by embedding vector within the current repository."""
        query_vector = format_vector(query_embedding)

        with get_db_session() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                        chunk_id,
                        point_id,
                        repo_id,
                        text,
                        source_type,
                        relative_path,
                        start_line,
                        end_line,
                        symbol_name,
                        qualified_name,
                        symbol_type,
                        heading,
                        embedding <=> CAST(:query_vector AS vector) AS distance
                    FROM chunk_embeddings
                    WHERE repo_id = :repo_id
                    ORDER BY embedding <=> CAST(:query_vector AS vector)
                    LIMIT :top_k
                    """
                ),
                {
                    "repo_id": sanitize_postgres_text_or_empty(self.repo_id),
                    "query_vector": query_vector,
                    "top_k": top_k,
                },
            ).mappings().all()

        results: list[dict[str, Any]] = []

        for row in rows:
            distance = float(row["distance"] or 0.0)
            score = 1.0 - distance
            text_value = sanitize_postgres_text_or_empty(row["text"])
            relative_path = sanitize_postgres_text_or_empty(row["relative_path"])

            payload = {
                "repo_id": sanitize_postgres_text_or_empty(row["repo_id"]),
                "chunk_id": sanitize_postgres_text_or_empty(row["chunk_id"]),
                "text": text_value,
                "source_type": sanitize_postgres_text(row["source_type"]),
                "relative_path": relative_path,
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "symbol_name": sanitize_postgres_text(row["symbol_name"]),
                "qualified_name": sanitize_postgres_text(row["qualified_name"]),
                "symbol_type": sanitize_postgres_text(row["symbol_type"]),
                "heading": sanitize_postgres_text(row["heading"]),
            }

            qualified_name = payload["qualified_name"]
            symbol_name = payload["symbol_name"]

            results.append(
                {
                    "id": str(row["point_id"]),
                    "score": score,
                    "vector_score": score,
                    "text": text_value,
                    "content": text_value,
                    "code": text_value,
                    "chunk_id": payload["chunk_id"],
                    "source_type": payload["source_type"],
                    "relative_path": relative_path,
                    "file_path": relative_path,
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "line_start": row["start_line"],
                    "line_end": row["end_line"],
                    "symbol_name": symbol_name,
                    "qualified_name": qualified_name,
                    "symbol": qualified_name or symbol_name,
                    "symbol_type": payload["symbol_type"],
                    "heading": payload["heading"],
                    "metadata": payload,
                }
            )

        return results

    def search(
        self,
        query: str | list[float] | None = None,
        top_k: int = 10,
        query_embedding: list[float] | None = None,
        query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """Compatibility search entrypoint supporting text or embedding queries."""
        if query_embedding is None and isinstance(query, list):
            query_embedding = query

        if query_text is None and isinstance(query, str):
            query_text = sanitize_postgres_text_or_empty(query)

        if query_embedding is None:
            if not query_text:
                raise ValueError("Either query text or query embedding must be provided")

            query_text = sanitize_postgres_text_or_empty(query_text)
            query_embedding = self.embedding_model.embed_query(query_text)

        return self.search_by_vector(
            query_embedding=query_embedding,
            top_k=top_k,
        )

    def search_text(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Search chunks by query text within the current repository."""
        query = sanitize_postgres_text_or_empty(query)
        query_embedding = self.embedding_model.embed_query(query)

        return self.search_by_vector(
            query_embedding=query_embedding,
            top_k=top_k,
        )
