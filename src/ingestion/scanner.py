"""
Scans a repository directory tree for supported source files.

Respects IGNORE_DIRS from constants to skip build artifacts,
virtual environments, caches, etc.
"""

from pathlib import Path
from typing import List

from src.constants import IGNORE_DIRS, SUPPORTED_EXTENSIONS
from src.ingestion.file_type_detector import is_supported


def _should_ignore(path: Path) -> bool:
    """Return True if any path component matches IGNORE_DIRS."""
    parts = set(path.parts)
    return bool(parts & IGNORE_DIRS)


def scan_repository(repo_path: str | Path) -> List[Path]:
    """
    Recursively scan *repo_path* and return all supported files.

    Args:
        repo_path: Absolute or relative path to a repository directory.

    Returns:
        Sorted list of ``Path`` objects for each supported file.

    Raises:
        FileNotFoundError: If *repo_path* does not exist.
        NotADirectoryError: If *repo_path* is not a directory.
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
        if is_supported(path):
            files.append(path)

    return sorted(files)
