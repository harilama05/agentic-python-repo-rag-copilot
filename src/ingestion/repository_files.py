"""
Helpers for preparing repository-like inputs before indexing.

GitHub clones and ZIP uploads can contain many files that the RAG pipeline
should not ingest. This module centralizes directory traversal and keeps only
the file formats accepted by those ingestion paths.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List

from src.constants import IGNORE_DIRS


INGESTIBLE_REPOSITORY_EXTENSIONS = {".txt", ".py", ".json", ".md"}


@dataclass
class PreparedRepository:
    """A local repository directory plus the files selected for indexing."""

    repo_id: str
    name: str
    local_path: Path
    files: List[Path]
    ignored_file_count: int = 0
    metadata: dict[str, str | None] = field(default_factory=dict)

    @property
    def file_count(self) -> int:
        return len(self.files)


def _should_ignore(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & IGNORE_DIRS)


def is_ingestible_repository_file(path: str | Path) -> bool:
    """Return True for file types accepted from GitHub and ZIP repositories."""
    return Path(path).suffix.lower() in INGESTIBLE_REPOSITORY_EXTENSIONS


def collect_ingestible_repository_files(repo_path: str | Path) -> List[Path]:
    """
    Traverse a repository directory and return supported files only.

    Supported extensions for GitHub/ZIP ingestion are intentionally limited to
    .txt, .py, .json, and .md.
    """
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    files: List[Path] = []

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if _should_ignore(path):
            continue
        if is_ingestible_repository_file(path):
            files.append(path.resolve())

    return sorted(files)


def count_ignored_repository_files(
    repo_path: str | Path,
    selected_files: Iterable[Path],
) -> int:
    """Count traversed files that were skipped by the GitHub/ZIP filter."""
    repo_path = Path(repo_path).resolve()
    selected = {Path(path).resolve() for path in selected_files}
    ignored = 0

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if _should_ignore(path):
            continue
        if path.resolve() not in selected:
            ignored += 1

    return ignored


def prepare_local_repository(
    repo_path: str | Path,
    *,
    repo_id: str,
    name: str,
    metadata: dict[str, str | None] | None = None,
) -> PreparedRepository:
    """
    Build a PreparedRepository from an existing local directory.

    Raises ValueError when no supported files are found so API callers can
    return a clean 400 response instead of indexing an empty repository.
    """
    local_path = Path(repo_path).resolve()
    files = collect_ingestible_repository_files(local_path)

    if not files:
        allowed = ", ".join(sorted(INGESTIBLE_REPOSITORY_EXTENSIONS))
        raise ValueError(f"No supported files found. Allowed extensions: {allowed}")

    return PreparedRepository(
        repo_id=repo_id,
        name=name,
        local_path=local_path,
        files=files,
        ignored_file_count=count_ignored_repository_files(local_path, files),
        metadata=metadata or {},
    )
