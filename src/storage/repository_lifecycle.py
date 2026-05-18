import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy import delete, select

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
    source_type: str | None
    is_persistent: bool
    local_path: str | None

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
            source_type=getattr(repo, "source_type", None),
            is_persistent=bool(getattr(repo, "is_persistent", False)),
            local_path=getattr(repo, "local_path", None),
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