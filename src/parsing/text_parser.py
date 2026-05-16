"""
Plain text parser — wraps raw text files into ParsedDocument.
"""

from pathlib import Path
from typing import Optional

from src.schemas import FileType, ParsedDocument


def parse_text_file(
    file_path: str | Path,
    relative_path: Optional[str] = None,
) -> ParsedDocument:
    """Parse a plain text file."""
    file_path = Path(file_path).resolve()
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    rel = relative_path or str(file_path)

    return ParsedDocument(
        file_path=str(file_path),
        relative_path=rel,
        file_type=FileType.TEXT,
        source_code=source,
    )
