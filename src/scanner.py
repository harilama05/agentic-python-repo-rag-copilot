from pathlib import Path
from typing import List

from src.config import IGNORE_DIRS, SUPPORTED_EXTENSIONS


def should_ignore_path(path: Path) -> bool:
    """
    Return True if the path should be ignored based on directory names.
    """
    parts = set(path.parts)

    for ignored_dir in IGNORE_DIRS:
        if ignored_dir in parts:
            return True

    return False


def is_supported_python_file(path: Path) -> bool:
    """
    Return True if the path is a valid Python source file.
    """
    return (
        path.is_file()
        and path.suffix in SUPPORTED_EXTENSIONS
        and not should_ignore_path(path)
    )


def scan_python_files(repo_path: str | Path) -> List[Path]:
    """
    Scan a repository and return all valid Python files.

    Args:
        repo_path: Path to the Python repository.

    Returns:
        List of Python file paths.
    """
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repo path is not a directory: {repo_path}")

    python_files = []

    for path in repo_path.rglob("*.py"):
        if is_supported_python_file(path):
            python_files.append(path)

    return sorted(python_files)