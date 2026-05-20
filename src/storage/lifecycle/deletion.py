import os
import shutil
import stat
import time
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy import delete

from src.core.config import RUNTIME_DIR
from src.core.settings import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL
from src.db.models import Chunk, CodeEdge, CodeNode, Repository
from src.db.session import get_db_session
from src.storage.lifecycle.models import is_temporary_repository
from src.storage.lifecycle.queries import get_repository_snapshot

def delete_qdrant_points_for_repo(repo_id: str) -> None:
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
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise

def _safe_rmtree(path: Path, retries: int = 3, delay_seconds: float = 0.3) -> None:
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
