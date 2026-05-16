"""
YAML parser — loads YAML and converts to readable text for indexing.
"""

from pathlib import Path
from typing import Optional

import yaml

from src.schemas import FileType, ParsedDocument


def parse_yaml_file(
    file_path: str | Path,
    relative_path: Optional[str] = None,
) -> ParsedDocument:
    """Parse a YAML file into a ParsedDocument."""
    file_path = Path(file_path).resolve()
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    rel = relative_path or str(file_path)

    # Re-serialize for consistent formatting
    try:
        data = yaml.safe_load(raw)
        source = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    except yaml.YAMLError:
        source = raw

    return ParsedDocument(
        file_path=str(file_path),
        relative_path=rel,
        file_type=FileType.YAML,
        source_code=source,
    )
