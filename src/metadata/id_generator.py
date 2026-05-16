"""
Deterministic chunk ID generator.

Produces content-addressable IDs so re-indexing the same file produces
identical chunk IDs — enabling incremental updates.
"""

import hashlib


def generate_chunk_id(
    file_path: str,
    qualified_name: str | None = None,
    start_line: int = 0,
    end_line: int = 0,
    chunk_index: int | None = None,
) -> str:
    """
    Create a deterministic MD5-based chunk ID.

    For code chunks the ID is based on file + symbol + lines.
    For text chunks the ID is based on file + chunk index.
    """
    if qualified_name:
        raw = f"{file_path}:{qualified_name}:{start_line}:{end_line}"
    elif chunk_index is not None:
        raw = f"{file_path}:chunk:{chunk_index}"
    else:
        raw = f"{file_path}:{start_line}:{end_line}"

    return hashlib.md5(raw.encode("utf-8")).hexdigest()
