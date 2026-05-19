import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select, func
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from src.config import RUNTIME_DIR
from src.constants import TEMPORARY_REPO_SOURCE_TYPES
from src.db.models import Chunk, CodeEdge, CodeNode, Repository
from src.db.session import get_db_session
from src.settings import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL
import os
import stat
import time

@dataclass
class RepositorySnapshot:
    repo_id: str
    repo_name: str
    source_type: str | None
    is_persistent: bool
    local_path: str | None
    collection_name: str | None
    file_count: int
    doc_count: int
    ignored_file_count: int
    chunk_count: int

@dataclass
class RepositoryListItem:
    repo_id: str
    repo_name: str
    source_type: str | None
    is_persistent: bool
    local_path: str | None
    collection_name: str | None
    chunk_count: int

@dataclass
class TemporaryRepositoryItem:
    repo_id: str
    repo_name: str
    source_type: str | None
    is_persistent: bool
    local_path: str | None
    expires_at: datetime | None

def is_temporary_repository(source_type: str | None, is_persistent: bool | None) -> bool:
    """
    A temporary repo is a user-provided repo that should be removed when
    the user switches away or uploads another temporary repo.
    """
    if is_persistent:
        return False

    return source_type in TEMPORARY_REPO_SOURCE_TYPES


def get_repository_snapshot(repo_id: str) -> Optional[RepositorySnapshot]:
    """
    Load only the repository fields needed for lifecycle cleanup.

    Do not return a SQLAlchemy ORM object outside the session, because it can
    become detached after the session closes.
    """
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


def delete_qdrant_points_for_repo(repo_id: str) -> None:
    """
    Delete all Qdrant vectors belonging to a repo_id.
    """
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY or None,
    )

    collections = client.get_collections().collections
    collection_names = {collection.name for collection in collections}

    if QDRANT_COLLECTION not in collection_names:
        return

    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=qdrant_models.FilterSelector(
            filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="repo_id",
                        match=qdrant_models.MatchValue(value=repo_id),
                    )
                ]
            )
        ),
        wait=True,
    )


def delete_postgres_rows_for_repo(repo_id: str) -> None:
    """
    Delete repository metadata from PostgreSQL.

    Delete child tables first, then repository row.
    """
    with get_db_session() as session:
        session.execute(delete(CodeEdge).where(CodeEdge.repo_id == repo_id))
        session.execute(delete(CodeNode).where(CodeNode.repo_id == repo_id))
        session.execute(delete(Chunk).where(Chunk.repo_id == repo_id))
        session.execute(delete(Repository).where(Repository.repo_id == repo_id))
        session.commit()


def _is_under_runtime_dir(path: Path) -> bool:
    try:
        path.resolve().relative_to(RUNTIME_DIR.resolve())
        return True
    except ValueError:
        return False


def _find_runtime_repo_dir(local_path: str | None, repo_id: str) -> Optional[Path]:
    """
    Find the top runtime folder for a temp repo.

    Examples:
    - data/runtime/github/<repo_id>/...
    - data/runtime/uploads/<repo_id>/extracted/...
    """
    if not local_path:
        return None

    path = Path(local_path)

    if not path.exists():
        return None

    path = path.resolve()

    for candidate in [path, *path.parents]:
        if candidate.name == repo_id and _is_under_runtime_dir(candidate):
            return candidate

    if _is_under_runtime_dir(path):
        return path

    return None


def _handle_remove_readonly(func, path, exc_info):
    """
    Make read-only files writable and retry deletion.

    This is useful on Windows when deleting Git object files inside .git.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def _safe_rmtree(path: Path, retries: int = 3, delay_seconds: float = 0.3) -> None:
    """
    Remove a directory with retries.

    Windows can temporarily lock .git pack files, so retry a few times.
    If deletion still fails, rename the folder to a delete-pending name so
    it no longer blocks the next clone/index operation.
    """
    if not path.exists():
        return

    last_error = None

    for _ in range(retries):
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay_seconds)

    pending_path = path.with_name(f"{path.name}__delete_pending")

    try:
        if pending_path.exists():
            shutil.rmtree(pending_path, onerror=_handle_remove_readonly)

        path.rename(pending_path)

    except Exception:
        if last_error is not None:
            raise last_error
        raise


def delete_runtime_files_for_repo(repo_id: str, local_path: str | None) -> None:
    runtime_repo_dir = _find_runtime_repo_dir(
        local_path=local_path,
        repo_id=repo_id,
    )

    if runtime_repo_dir is None:
        return

    if runtime_repo_dir.exists() and runtime_repo_dir.is_dir():
        _safe_rmtree(runtime_repo_dir)

def delete_repository(
    repo_id: str,
    *,
    delete_runtime_files: bool = True,
    only_if_temporary: bool = False,
) -> bool:
    """
    Delete a repository from Qdrant, PostgreSQL, and optionally runtime files.

    If only_if_temporary=True, persistent/company repos will never be deleted.
    Returns True if a repository was deleted.
    """
    repo = get_repository_snapshot(repo_id)

    if repo is None:
        return False

    source_type = repo.source_type
    is_persistent = repo.is_persistent
    local_path = repo.local_path

    if only_if_temporary and not is_temporary_repository(source_type, is_persistent):
        return False

    delete_qdrant_points_for_repo(repo_id)
    delete_postgres_rows_for_repo(repo_id)

    if delete_runtime_files:
        delete_runtime_files_for_repo(
            repo_id=repo_id,
            local_path=local_path,
        )

    return True


def cleanup_temporary_repository(repo_id: str | None) -> bool:
    """
    Cleanup one temporary repository safely.
    """
    if not repo_id:
        return False

    return delete_repository(
        repo_id=repo_id,
        delete_runtime_files=True,
        only_if_temporary=True,
    )

def list_persistent_repositories() -> list[RepositoryListItem]:
    """
    List repositories that should be loadable without re-indexing.

    This is mainly for company/admin-indexed repositories.
    """
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
    """
    List temporary repositories whose expires_at is already reached.

    Temporary repos are user-provided GitHub/ZIP repos:
    - is_persistent = False
    - source_type in TEMPORARY_REPO_SOURCE_TYPES
    - expires_at <= now
    """
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
    
def cleanup_expired_temporary_repositories(
    *,
    dry_run: bool = False,
) -> list[str]:
    """
    Delete expired temporary repositories.

    Returns the repo_ids that were deleted, or would be deleted in dry-run mode.
    """
    expired_repos = list_expired_temporary_repositories()

    repo_ids: list[str] = []

    for repo in expired_repos:
        repo_ids.append(repo.repo_id)

        if dry_run:
            continue

        delete_repository(
            repo_id=repo.repo_id,
            delete_runtime_files=True,
            only_if_temporary=True,
        )

    return repo_ids