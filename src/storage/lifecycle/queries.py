from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from src.db.models import Chunk, Repository
from src.db.session import get_db_session
from src.storage.lifecycle.models import (
    RepositoryListItem,
    RepositorySnapshot,
    TemporaryRepositoryItem,
    is_temporary_repository,
)

def get_repository_snapshot(repo_id: str) -> Optional[RepositorySnapshot]:
    with get_db_session() as session:
        repo = session.execute(
            select(Repository).where(Repository.repo_id == repo_id)
        ).scalar_one_or_none()

        if repo is None:
            return None

        return RepositorySnapshot(
            repo_id=repo.repo_id,
            repo_name=(
                getattr(repo, "repo_name", None)
                or getattr(repo, "name", None)
                or repo.repo_id
            ),
            source_type=getattr(repo, "source_type", None),
            is_persistent=bool(getattr(repo, "is_persistent", False)),
            local_path=getattr(repo, "local_path", None),
            collection_name=(
                getattr(repo, "collection_name", None)
                or repo.repo_id
            ),
            file_count=int(getattr(repo, "file_count", 0) or 0),
            doc_count=int(getattr(repo, "doc_count", 0) or 0),
            ignored_file_count=int(getattr(repo, "ignored_file_count", 0) or 0),
            chunk_count=int(getattr(repo, "chunk_count", 0) or 0),
        )

def list_persistent_repositories() -> list[RepositoryListItem]:
    with get_db_session() as session:
        repos = session.execute(
            select(Repository).where(Repository.is_persistent.is_(True))
        ).scalars().all()

        items: list[RepositoryListItem] = []

        for repo in repos:
            repo_id = repo.repo_id

            chunk_count = session.execute(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.repo_id == repo_id)
            ).scalar_one()

            repo_name = (
                getattr(repo, "repo_name", None)
                or getattr(repo, "name", None)
                or repo_id
            )

            collection_name = (
                getattr(repo, "collection_name", None)
                or repo_id
            )

            items.append(
                RepositoryListItem(
                    repo_id=repo_id,
                    repo_name=repo_name,
                    source_type=getattr(repo, "source_type", None),
                    is_persistent=bool(getattr(repo, "is_persistent", False)),
                    local_path=getattr(repo, "local_path", None),
                    collection_name=collection_name,
                    chunk_count=int(chunk_count or 0),
                )
            )

        return items

def list_expired_temporary_repositories(
    now: datetime | None = None,
) -> list[TemporaryRepositoryItem]:
    if now is None:
        now = datetime.now(timezone.utc)

    with get_db_session() as session:
        repos = session.execute(
            select(Repository).where(
                Repository.is_persistent.is_(False),
                Repository.expires_at.is_not(None),
                Repository.expires_at <= now,
            )
        ).scalars().all()

        items: list[TemporaryRepositoryItem] = []

        for repo in repos:
            source_type = getattr(repo, "source_type", None)
            is_persistent = bool(getattr(repo, "is_persistent", False))

            if not is_temporary_repository(source_type, is_persistent):
                continue

            repo_name = (
                getattr(repo, "repo_name", None)
                or getattr(repo, "name", None)
                or repo.repo_id
            )

            items.append(
                TemporaryRepositoryItem(
                    repo_id=repo.repo_id,
                    repo_name=repo_name,
                    source_type=source_type,
                    is_persistent=is_persistent,
                    local_path=getattr(repo, "local_path", None),
                    expires_at=getattr(repo, "expires_at", None),
                )
            )

        return items
