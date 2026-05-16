"""
Text chunker — splits plain text using sliding window with overlap.

Uses a character-based window with sentence-boundary awareness so that
chunks don't break mid-sentence.
"""

from typing import List

from src.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from src.schemas import ParsedDocument
from src.chunking.chunk_models import ChunkResult


def _split_with_overlap(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """
    Split *text* into overlapping windows.

    Tries to break at sentence boundaries (``\\n`` or ``. ``) when possible.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look backward for a paragraph break
            newline_pos = text.rfind("\n\n", start, end)
            if newline_pos > start + chunk_size // 2:
                end = newline_pos + 2
            else:
                # Look backward for a sentence break
                period_pos = text.rfind(". ", start, end)
                if period_pos > start + chunk_size // 2:
                    end = period_pos + 2

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward by (end - overlap)
        start = max(start + 1, end - overlap)

    return chunks


def chunk_text(
    doc: ParsedDocument,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[ChunkResult]:
    """
    Split a text document into overlapping chunks.
    """
    segments = _split_with_overlap(doc.source_code, chunk_size, overlap)
    results: List[ChunkResult] = []

    for i, segment in enumerate(segments):
        preamble = f"File: {doc.relative_path}\nChunk: {i + 1}/{len(segments)}\n\n"
        text = preamble + segment

        results.append(
            ChunkResult(
                text=text,
                content=segment,
                symbol_name=None,
                qualified_name=None,
                symbol_type=None,
                start_line=0,
                end_line=0,
                extra_metadata={"chunk_index": i, "total_chunks": len(segments)},
            )
        )

    return results
