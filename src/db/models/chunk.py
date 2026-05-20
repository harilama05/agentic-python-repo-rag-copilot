from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base, utc_now
from src.db.models.repository import Repository


class Chunk(Base):
    """
    Metadata and text for one indexed chunk.

    Embeddings are stored in Qdrant.
    Chunk metadata/text is stored here for source display, debugging,
    and mapping retrieval results back to code locations.
    """

    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    repo_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("repositories.repo_id", ondelete="CASCADE"),
        nullable=False,
    )

    # code / documentation
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    relative_path: Mapped[str] = mapped_column(Text, nullable=False)

    start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    symbol_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qualified_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    symbol_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    heading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    repository: Mapped["Repository"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_repo_id", "repo_id"),
        Index("idx_chunks_repo_path", "repo_id", "relative_path"),
        Index("idx_chunks_repo_symbol", "repo_id", "qualified_name"),
    )
