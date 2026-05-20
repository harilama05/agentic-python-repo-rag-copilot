from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base, utc_now

class Repository(Base):
    """
    A repository indexed by the system.

    Company repositories are persistent.
    User GitHub/ZIP repositories can be temporary and expire later.
    """

    __tablename__ = "repositories"

    repo_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # company / github / zip / custom_local
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # company / private_session / private_user later
    visibility: Mapped[str] = mapped_column(String(50), nullable=False)

    is_persistent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    owner_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    commit_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    collection_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # indexing / indexed / failed
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    doc_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ignored_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    code_nodes: Mapped[list["CodeNode"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    code_edges: Mapped[list["CodeEdge"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    index_jobs: Mapped[list["IndexJob"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
