from typing import Any, Iterable

from sqlalchemy import delete, select

from src.db.models import Chunk
from src.db.session import get_db_session
from src.storage.metadata.utils import (
    get_chunk_metadata,
    get_chunk_text,
    get_metadata_value,
    make_stable_chunk_id,
    sanitize_postgres_text,
    sanitize_postgres_text_or_empty,
)


class ChunkStoreMixin:
    def replace_chunks(
        self,
        *,
        repo_id: str,
        chunks: Iterable[Any],
    ) -> None:
        with get_db_session() as session:
            session.execute(
                delete(Chunk).where(Chunk.repo_id == repo_id)
            )

            chunk_rows: list[Chunk] = []

            for chunk in chunks:
                metadata = get_chunk_metadata(chunk)
                text = sanitize_postgres_text_or_empty(get_chunk_text(chunk))

                relative_path = get_metadata_value(
                    metadata,
                    "relative_path",
                    "file_path",
                    "path",
                    default="",
                )
                relative_path = sanitize_postgres_text_or_empty(relative_path)

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
                        repo_id=repo_id,
                        relative_path=relative_path,
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

                chunk_rows.append(
                    Chunk(
                        chunk_id=sanitize_postgres_text_or_empty(chunk_id),
                        repo_id=sanitize_postgres_text_or_empty(repo_id),
                        source_type=sanitize_postgres_text(source_type),
                        relative_path=relative_path,
                        start_line=start_line,
                        end_line=end_line,
                        symbol_name=sanitize_postgres_text(symbol_name),
                        qualified_name=sanitize_postgres_text(qualified_name),
                        symbol_type=sanitize_postgres_text(symbol_type),
                        heading=sanitize_postgres_text(heading),
                        text=text,
                    )
                )

            session.add_all(chunk_rows)

    def load_chunks(self, repo_id: str) -> list[dict[str, Any]]:
        with get_db_session() as session:
            rows = session.execute(
                select(Chunk)
                .where(Chunk.repo_id == repo_id)
                .order_by(Chunk.relative_path, Chunk.start_line, Chunk.chunk_id)
            ).scalars().all()

            chunks: list[dict[str, Any]] = []

            for row in rows:
                row_text = sanitize_postgres_text_or_empty(row.text)
                relative_path = sanitize_postgres_text_or_empty(row.relative_path)
                qualified_name = sanitize_postgres_text(row.qualified_name)
                symbol_name = sanitize_postgres_text(row.symbol_name)

                metadata = {
                    "chunk_id": sanitize_postgres_text_or_empty(row.chunk_id),
                    "repo_id": sanitize_postgres_text_or_empty(row.repo_id),
                    "source_type": sanitize_postgres_text(row.source_type),
                    "relative_path": relative_path,
                    "file_path": relative_path,
                    "start_line": row.start_line,
                    "end_line": row.end_line,
                    "line_start": row.start_line,
                    "line_end": row.end_line,
                    "symbol_name": symbol_name,
                    "qualified_name": qualified_name,
                    "symbol": qualified_name or symbol_name,
                    "symbol_type": sanitize_postgres_text(row.symbol_type),
                    "heading": sanitize_postgres_text(row.heading),
                }

                chunks.append(
                    {
                        "chunk_id": metadata["chunk_id"],
                        "repo_id": metadata["repo_id"],
                        "source_type": metadata["source_type"],
                        "relative_path": relative_path,
                        "file_path": relative_path,
                        "start_line": row.start_line,
                        "end_line": row.end_line,
                        "line_start": row.start_line,
                        "line_end": row.end_line,
                        "symbol_name": symbol_name,
                        "qualified_name": qualified_name,
                        "symbol": qualified_name or symbol_name,
                        "symbol_type": metadata["symbol_type"],
                        "heading": metadata["heading"],
                        "text": row_text,
                        "content": row_text,
                        "code": row_text,
                        "metadata": metadata,
                    }
                )

            return chunks

    def count_chunks(self, repo_id: str) -> int:
        with get_db_session() as session:
            result = session.execute(
                select(Chunk).where(Chunk.repo_id == repo_id)
            ).scalars().all()

            return len(result)
