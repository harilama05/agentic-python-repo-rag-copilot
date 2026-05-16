"""
Path traversal guard — prevents access outside allowed directories.
"""

from pathlib import Path

from src.config import settings


def is_safe_path(path: str | Path, allowed_root: str | Path | None = None) -> bool:
    """
    Check that *path* resolves inside *allowed_root*.

    Prevents directory traversal attacks (e.g. ``../../etc/passwd``).
    """
    if allowed_root is None:
        allowed_root = settings.project_root

    resolved = Path(path).resolve()
    root = Path(allowed_root).resolve()

    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_safe_path(path: str | Path, allowed_root: str | Path | None = None) -> Path:
    """
    Like ``is_safe_path`` but raises on violation.
    """
    if not is_safe_path(path, allowed_root):
        raise PermissionError(
            f"Path traversal blocked: {path} is outside allowed root."
        )
    return Path(path).resolve()
