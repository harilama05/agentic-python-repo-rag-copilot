"""
Plain text parser for repository indexing.

This parser reads .txt files and returns normalized text plus citation metadata.
"""

from pathlib import Path
from typing import Any, Dict


def parse_text_file(file_path: str | Path, repo_root: str | Path) -> Dict[str, Any]:
    """
    Parse a plain text file.
    """
    path = Path(file_path).resolve()
    root = Path(repo_root).resolve()

    relative_path = str(path.relative_to(root)).replace("\\", "/")

    text = path.read_text(encoding="utf-8", errors="ignore")

    return {
        "text": text,
        "metadata": {
            "relative_path": relative_path,
            "file_path": relative_path,
            "source_type": "text",
            "symbol_name": None,
            "qualified_name": relative_path,
            "symbol_type": "text_file",
            "heading": path.name,
        },
    }