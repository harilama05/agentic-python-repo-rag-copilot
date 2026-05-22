"""Repository file scanning utilities.

This module discovers files that should be indexed while applying the project's
ignore rules.
"""

from pathlib import Path
from typing import List

from src.core.constants import (
    IGNORE_DIRS,
    IGNORE_FILE_NAMES,
    JSON_EXTENSIONS,
    MAX_INDEX_FILE_BYTES,
    PYTHON_EXTENSIONS,
    TEXT_EXTENSIONS,
)


def should_ignore_path(path: Path) -> bool:
    """Return True if the path should be ignored based on directory names."""
    parts_lower = {part.lower() for part in path.parts}

    for ignored_dir in IGNORE_DIRS:
        if ignored_dir.lower() in parts_lower:
            return True

    return False


def should_ignore_file_name(path: Path) -> bool:
    """Return True if the file name should be ignored."""
    return path.name.lower() in IGNORE_FILE_NAMES


def is_within_index_size_limit(path: Path) -> bool:
    """Return True if the file is small enough to index."""
    if MAX_INDEX_FILE_BYTES is None:
        return True

    try:
        return path.stat().st_size <= MAX_INDEX_FILE_BYTES
    except OSError:
        return False


def is_supported_python_file(path: Path) -> bool:
    """Return True if the path is a valid Python source file."""
    return (
        path.is_file()
        and path.suffix.lower() in PYTHON_EXTENSIONS
        and not should_ignore_path(path)
        and not should_ignore_file_name(path)
        and is_within_index_size_limit(path)
    )


def is_supported_text_like_file(path: Path, extensions: set[str]) -> bool:
    """Return True if a JSON/TXT-like file should be indexed."""
    return (
        path.is_file()
        and path.suffix.lower() in extensions
        and not should_ignore_path(path)
        and not should_ignore_file_name(path)
        and is_within_index_size_limit(path)
    )


def scan_python_files(repo_path: str | Path) -> List[Path]:
    """Scan a repository and return all valid Python files."""
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repo path is not a directory: {repo_path}")

    python_files = []

    for path in repo_path.rglob("*"):
        if is_supported_python_file(path):
            python_files.append(path)

    return sorted(python_files)


def scan_json_files(repo_path: str | Path) -> list[Path]:
    """Scan JSON files in a repository."""
    repo_root = Path(repo_path).resolve()

    return sorted(
        path
        for path in repo_root.rglob("*")
        if is_supported_text_like_file(path, JSON_EXTENSIONS)
    )


def scan_text_files(repo_path: str | Path) -> list[Path]:
    """Scan TXT files in a repository."""
    repo_root = Path(repo_path).resolve()

    return sorted(
        path
        for path in repo_root.rglob("*")
        if is_supported_text_like_file(path, TEXT_EXTENSIONS)
    )