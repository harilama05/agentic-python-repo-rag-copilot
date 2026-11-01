"""Original indexed file contents, independent of retrieval chunk boundaries."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    repo_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("repositories.repo_id", ondelete="CASCADE"), primary_key=True,
    )
    relative_path: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
