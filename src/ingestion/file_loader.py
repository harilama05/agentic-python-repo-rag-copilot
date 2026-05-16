"""
Loads file content from disk and returns a raw text representation.

Handles encoding detection and graceful error recovery.
"""

from pathlib import Path
from typing import Optional


def load_file(
    file_path: str | Path,
    encoding: str = "utf-8",
) -> Optional[str]:
    """
    Read the entire contents of *file_path* as a string.

    Args:
        file_path: Path to the file.
        encoding: Text encoding to use (default ``utf-8``).

    Returns:
        File contents as a string, or ``None`` if the file cannot be read.
    """
    path = Path(file_path).resolve()

    if not path.is_file():
        return None

    try:
        return path.read_text(encoding=encoding, errors="ignore")
    except Exception:
        return None


def load_file_lines(
    file_path: str | Path,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    context_lines: int = 0,
    encoding: str = "utf-8",
) -> Optional[str]:
    """
    Load a specific line range from a file.

    Line numbers are 1-indexed. If *start_line* / *end_line* are ``None``,
    the entire file is returned.
    """
    content = load_file(file_path, encoding)
    if content is None:
        return None

    lines = content.splitlines()
    total = len(lines)

    if start_line is None:
        start_line = 1
    if end_line is None:
        end_line = total

    start_line = max(1, start_line - context_lines)
    end_line = min(total, end_line + context_lines)

    return "\n".join(lines[start_line - 1 : end_line])
