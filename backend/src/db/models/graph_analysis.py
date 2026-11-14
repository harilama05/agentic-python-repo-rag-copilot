"""Versioned graph evidence sidecar; legacy graph columns stay compatible."""

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class RepositoryGraphAnalysis(Base):
    __tablename__ = "repository_graph_analysis"

    repo_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("repositories.repo_id", ondelete="CASCADE"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
