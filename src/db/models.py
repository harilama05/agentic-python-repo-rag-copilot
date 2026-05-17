from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


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


class CodeNode(Base):
    """
    One node in the AST-based code graph.

    Examples:
    - function
    - class
    - method
    """

    __tablename__ = "code_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    repo_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("repositories.repo_id", ondelete="CASCADE"),
        nullable=False,
    )

    node_id: Mapped[str] = mapped_column(Text, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # function / class / method
    node_type: Mapped[str] = mapped_column(String(100), nullable=False)

    relative_path: Mapped[str] = mapped_column(Text, nullable=False)

    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    parent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    repository: Mapped["Repository"] = relationship(back_populates="code_nodes")

    __table_args__ = (
        UniqueConstraint("repo_id", "node_id", name="uq_code_nodes_repo_node"),
        Index("idx_code_nodes_repo_id", "repo_id"),
        Index("idx_code_nodes_repo_qualified_name", "repo_id", "qualified_name"),
        Index("idx_code_nodes_repo_path", "repo_id", "relative_path"),
    )


class CodeEdge(Base):
    """
    One edge in the AST-based code graph.

    Examples:
    - class contains method
    - function calls method
    """

    __tablename__ = "code_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    repo_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("repositories.repo_id", ondelete="CASCADE"),
        nullable=False,
    )

    source_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_node_id: Mapped[str] = mapped_column(Text, nullable=False)

    # calls / contains
    edge_type: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    repository: Mapped["Repository"] = relationship(back_populates="code_edges")

    __table_args__ = (
        UniqueConstraint(
            "repo_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            name="uq_code_edges_repo_source_target_type",
        ),
        Index("idx_code_edges_repo_id", "repo_id"),
        Index("idx_code_edges_repo_source", "repo_id", "source_node_id"),
        Index("idx_code_edges_repo_target", "repo_id", "target_node_id"),
    )


class IndexJob(Base):
    """
    Tracks indexing jobs for company repos, GitHub repos, and ZIP uploads.
    """

    __tablename__ = "index_jobs"

    job_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    repo_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("repositories.repo_id", ondelete="CASCADE"),
        nullable=False,
    )

    # company / github / zip / custom_local
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # pending / running / completed / failed
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    repository: Mapped["Repository"] = relationship(back_populates="index_jobs")

    __table_args__ = (
        Index("idx_index_jobs_repo_id", "repo_id"),
        Index("idx_index_jobs_status", "status"),
    )