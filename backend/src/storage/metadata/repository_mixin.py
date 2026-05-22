from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.models import Repository
from src.db.session import get_db_session
from src.storage.metadata.utils import utc_now


class RepositoryStoreMixin:
    def upsert_repository(
        self,
        *,
        repo_id: str,
        name: str,
        source_type: str,
        visibility: str,
        is_persistent: bool,
        collection_name: str,
        status: str,
        file_count: int,
        doc_count: int,
        ignored_file_count: int,
        chunk_count: int,
        local_path: str | None = None,
        github_url: str | None = None,
        branch: str | None = None,
        commit_hash: str | None = None,
        owner_session_id: str | None = None,
        owner_user_id: str | None = None,
        indexed_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        with get_db_session() as session:
            stmt = insert(Repository).values(
                repo_id=repo_id,
                name=name,
                source_type=source_type,
                visibility=visibility,
                is_persistent=is_persistent,
                owner_session_id=owner_session_id,
                owner_user_id=owner_user_id,
                local_path=local_path,
                github_url=github_url,
                branch=branch,
                commit_hash=commit_hash,
                collection_name=collection_name,
                status=status,
                file_count=file_count,
                doc_count=doc_count,
                ignored_file_count=ignored_file_count,
                chunk_count=chunk_count,
                indexed_at=indexed_at,
                expires_at=expires_at,
            )

            update_columns = {
                "name": stmt.excluded.name,
                "source_type": stmt.excluded.source_type,
                "visibility": stmt.excluded.visibility,
                "is_persistent": stmt.excluded.is_persistent,
                "owner_session_id": stmt.excluded.owner_session_id,
                "owner_user_id": stmt.excluded.owner_user_id,
                "local_path": stmt.excluded.local_path,
                "github_url": stmt.excluded.github_url,
                "branch": stmt.excluded.branch,
                "commit_hash": stmt.excluded.commit_hash,
                "collection_name": stmt.excluded.collection_name,
                "status": stmt.excluded.status,
                "file_count": stmt.excluded.file_count,
                "doc_count": stmt.excluded.doc_count,
                "ignored_file_count": stmt.excluded.ignored_file_count,
                "chunk_count": stmt.excluded.chunk_count,
                "indexed_at": stmt.excluded.indexed_at,
                "expires_at": stmt.excluded.expires_at,
                "updated_at": utc_now(),
            }

            stmt = stmt.on_conflict_do_update(
                index_elements=[Repository.repo_id],
                set_=update_columns,
            )

            session.execute(stmt)

    def get_repository(self, repo_id: str) -> dict[str, Any] | None:
        with get_db_session() as session:
            repo = session.get(Repository, repo_id)

            if repo is None:
                return None

            return {
                "repo_id": repo.repo_id,
                "name": repo.name,
                "source_type": repo.source_type,
                "visibility": repo.visibility,
                "is_persistent": repo.is_persistent,
                "collection_name": repo.collection_name,
                "status": repo.status,
                "file_count": repo.file_count,
                "doc_count": repo.doc_count,
                "ignored_file_count": repo.ignored_file_count,
                "chunk_count": repo.chunk_count,
                "indexed_at": repo.indexed_at,
                "expires_at": repo.expires_at,
            }

    def list_repositories(self) -> list[dict[str, Any]]:
        with get_db_session() as session:
            repos = session.execute(
                select(Repository).order_by(Repository.updated_at.desc())
            ).scalars().all()

            return [
                {
                    "repo_id": repo.repo_id,
                    "name": repo.name,
                    "source_type": repo.source_type,
                    "visibility": repo.visibility,
                    "is_persistent": repo.is_persistent,
                    "collection_name": repo.collection_name,
                    "status": repo.status,
                    "file_count": repo.file_count,
                    "doc_count": repo.doc_count,
                    "ignored_file_count": repo.ignored_file_count,
                    "chunk_count": repo.chunk_count,
                    "indexed_at": repo.indexed_at,
                    "expires_at": repo.expires_at,
                }
                for repo in repos
            ]
