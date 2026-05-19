"""
JSON parser for repository indexing.

This parser reads JSON files safely and converts them into stable text that can
be chunked and embedded. It preserves file metadata for citations.
"""

import json
from pathlib import Path
from typing import Any, Dict


def parse_json_file(file_path: str | Path, repo_root: str | Path) -> Dict[str, Any]:
    """
    Parse a JSON file and return normalized text + metadata.

    The JSON content is pretty-printed so retrieval can match keys and values.
    """
    path = Path(file_path).resolve()
    root = Path(repo_root).resolve()

    relative_path = str(path.relative_to(root)).replace("\\", "/")

    raw_text = path.read_text(encoding="utf-8", errors="ignore")

    try:
        data = json.loads(raw_text)
        text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
        valid_json = True
        parse_error = None
    except Exception as exc:
        text = raw_text
        valid_json = False
        parse_error = str(exc)

    return {
        "text": text,
        "metadata": {
            "relative_path": relative_path,
            "file_path": relative_path,
            "source_type": "json",
            "symbol_name": None,
            "qualified_name": relative_path,
            "symbol_type": "json_file",
            "heading": path.name,
            "valid_json": valid_json,
            "parse_error": parse_error,
        },
    }