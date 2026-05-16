"""
JSON parser — loads JSON and converts to readable text for indexing.
"""

import json
from pathlib import Path
from typing import Optional

from src.schemas import FileType, ParsedDocument


def parse_json_file(
    file_path: str | Path,
    relative_path: Optional[str] = None,
) -> ParsedDocument:
    """Parse a JSON file into a ParsedDocument."""
    file_path = Path(file_path).resolve()
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    rel = relative_path or str(file_path)

    # Pretty-print for readability
    try:
        data = json.loads(raw)
        source = json.dumps(data, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        source = raw

    return ParsedDocument(
        file_path=str(file_path),
        relative_path=rel,
        file_type=FileType.JSON,
        source_code=source,
    )
