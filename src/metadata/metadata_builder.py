"""
Builds rich metadata dictionaries for chunks.

Metadata is stored alongside the vector embedding in ChromaDB and is
used for filtering, re-ranking, and citation building.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from src.schemas import ChunkType, SourceType
from src.chunking.chunk_models import ChunkResult
from src.metadata.id_generator import generate_chunk_id


def build_chunk_metadata(
    chunk_result: ChunkResult,
    file_path: str,
    relative_path: str,
    chunk_type: ChunkType,
    source: SourceType = SourceType.REPO,
    language: str = "python",
    chunk_index: int = 0,
) -> Dict[str, Any]:
    """
    Build a flat metadata dict suitable for ChromaDB storage.

    ChromaDB only supports str / int / float / bool values — all None
    values are converted to empty strings.
    """
    chunk_id = generate_chunk_id(
        file_path=file_path,
        qualified_name=chunk_result.qualified_name,
        start_line=chunk_result.start_line,
        end_line=chunk_result.end_line,
        chunk_index=chunk_index if not chunk_result.qualified_name else None,
    )

    metadata: Dict[str, Any] = {
        "chunk_id": chunk_id,
        "file_path": file_path,
        "relative_path": relative_path,
        "symbol_name": chunk_result.symbol_name or "",
        "qualified_name": chunk_result.qualified_name or "",
        "symbol_type": chunk_result.symbol_type or "",
        "start_line": chunk_result.start_line,
        "end_line": chunk_result.end_line,
        "parent": chunk_result.parent or "",
        "docstring": chunk_result.docstring or "",
        "chunk_type": chunk_type.value,
        "source": source.value,
        "language": language,
    }

    # Merge extra metadata
    for key, value in chunk_result.extra_metadata.items():
        if value is None:
            metadata[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = str(value)

    return metadata


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata values for ChromaDB compatibility.

    Converts None to "" and non-primitive types to str.
    """
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized
