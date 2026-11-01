"""Persist exact source snapshots for DB-only file reading and citations."""

from sqlalchemy import delete, inspect, select

from src.db.models import RepositoryFile
from src.db.session import engine, get_db_session


class FileStoreMixin:
    def replace_files(self, repo_id: str, files: dict[str, str]) -> None:
        # Additive migration for installations initialized before source snapshots.
        RepositoryFile.__table__.create(bind=engine, checkfirst=True)
        with get_db_session() as session:
            session.execute(delete(RepositoryFile).where(RepositoryFile.repo_id == repo_id))
            session.add_all([
                RepositoryFile(repo_id=repo_id, relative_path=path, content=content.replace("\x00", ""))
                for path, content in files.items()
            ])

    def load_files(self, repo_id: str) -> dict[str, str]:
        # Older indexes stay loadable; tools explicitly report partial reconstruction.
        if not inspect(engine).has_table("repository_files"):
            return {}
        with get_db_session() as session:
            rows = session.execute(
                select(RepositoryFile).where(RepositoryFile.repo_id == repo_id)
            ).scalars().all()
            return {row.relative_path: row.content for row in rows}
