"""Repository file scanning utilities.

This module discovers Python source files that should be indexed while applying
the project's ignore rules.
"""

from pathlib import Path
from typing import List

from src.core.constants import IGNORE_DIRS, PYTHON_EXTENSIONS
from src.core.constants import JSON_EXTENSIONS, TEXT_EXTENSIONS, IGNORE_DIRS

def should_ignore_path(path: Path) -> bool:
    """Return True if the path should be ignored based on directory names."""
    parts = set(path.parts)

    for ignored_dir in IGNORE_DIRS:
        if ignored_dir in parts:
            return True

    return False


def is_supported_python_file(path: Path) -> bool:
    """Return True if the path is a valid Python source file."""
    return (
        path.is_file()
        and path.suffix.lower() in PYTHON_EXTENSIONS
        and not should_ignore_path(path)
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
    """
    Scan JSON files in a repository.
    """
    repo_root = Path(repo_path).resolve()
    files: list[Path] = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        if path.suffix.lower() in JSON_EXTENSIONS:
            files.append(path)

    return sorted(files)


def scan_text_files(repo_path: str | Path) -> list[Path]:
    """
    Scan TXT files in a repository.
    """
    repo_root = Path(repo_path).resolve()
    files: list[Path] = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        if path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)

    return sorted(files)