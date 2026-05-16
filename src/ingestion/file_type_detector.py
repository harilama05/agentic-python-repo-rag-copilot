"""
Detects file type based on extension and optional content heuristics.
"""

from pathlib import Path

from src.schemas import FileType
from src.constants import (
    SUPPORTED_CODE_EXTENSIONS,
    SUPPORTED_CONFIG_EXTENSIONS,
    SUPPORTED_DOC_EXTENSIONS,
)

_EXTENSION_MAP: dict[str, FileType] = {
    ".py": FileType.PYTHON,
    ".md": FileType.MARKDOWN,
    ".txt": FileType.TEXT,
    ".rst": FileType.TEXT,
    ".json": FileType.JSON,
    ".yaml": FileType.YAML,
    ".yml": FileType.YAML,
}


def detect_file_type(path: str | Path) -> FileType:
    """
    Determine the FileType of a path based on its extension.

    Falls back to ``FileType.UNKNOWN`` for unsupported extensions.
    """
    suffix = Path(path).suffix.lower()
    return _EXTENSION_MAP.get(suffix, FileType.UNKNOWN)


def is_supported(path: str | Path) -> bool:
    """Return True if the file extension is supported."""
    suffix = Path(path).suffix.lower()
    return suffix in (
        SUPPORTED_CODE_EXTENSIONS | SUPPORTED_DOC_EXTENSIONS | SUPPORTED_CONFIG_EXTENSIONS
    )
