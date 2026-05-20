from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base, utc_now


class ChunkEmbedding(Base):
    """
    Vector embedding for one indexed chunk.

    The `embedding` column is created by `scripts.init_db` because it uses the
    Supabase/Postgres pgvector extension type.
    """

    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    repo_id: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int | None] = mapped_column(nullable=True)
    end_line: Mapped[int | None] = mapped_column(nullable=True)
    symbol_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qualified_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    symbol_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index("idx_chunk_embeddings_repo_id", "repo_id"),
        Index("idx_chunk_embeddings_repo_path", "repo_id", "relative_path"),
        Index("idx_chunk_embeddings_repo_symbol", "repo_id", "qualified_name"),
    )
