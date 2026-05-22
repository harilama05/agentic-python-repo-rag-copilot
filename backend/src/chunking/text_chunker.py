"""
Generic line-based text chunker.

Used for JSON and TXT files. It creates chunks with line ranges so citations can
point back to the original file.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class TextChunk:
    """
    Generic chunk object compatible with vector stores and MetadataStore.
    """
    chunk_id: str
    text: str
    metadata: Dict[str, Any]


def make_text_chunk_id(
    relative_path: str,
    start_line: int,
    end_line: int,
    text: str,
) -> str:
    """
    Create a stable chunk ID from file path, line range, and text.
    """
    raw = f"{relative_path}:{start_line}:{end_line}:{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_text_chunks(
    parsed: Dict[str, Any],
    max_lines: int = 80,
    overlap_lines: int = 10,
) -> List[TextChunk]:
    """
    Build line-based chunks from parsed text/json content.
    """
    text = parsed["text"]
    base_metadata = dict(parsed["metadata"])

    lines = text.splitlines()

    if not lines:
        return []

    relative_path = base_metadata.get("relative_path", "")

    chunks: List[TextChunk] = []
    start = 0

    while start < len(lines):
        end = min(start + max_lines, len(lines))

        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines)

        start_line = start + 1
        end_line = end

        metadata = dict(base_metadata)
        metadata.update(
            {
                "start_line": start_line,
                "end_line": end_line,
                "line_start": start_line,
                "line_end": end_line,
                "qualified_name": (
                    base_metadata.get("qualified_name")
                    or f"{relative_path}:{start_line}-{end_line}"
                ),
            }
        )

        chunk_id = make_text_chunk_id(
            relative_path=relative_path,
            start_line=start_line,
            end_line=end_line,
            text=chunk_text,
        )

        metadata["chunk_id"] = chunk_id

        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                text=chunk_text,
                metadata=metadata,
            )
        )

        if end >= len(lines):
            break

        start = max(end - overlap_lines, start + 1)

    return chunks
