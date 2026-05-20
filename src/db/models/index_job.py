from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base, utc_now
from src.db.models.repository import Repository


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
