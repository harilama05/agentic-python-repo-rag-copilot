from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base, utc_now
from src.db.models.repository import Repository


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
