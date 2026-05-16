"""
Markdown chunker — splits markdown by headings to create semantically
coherent chunks.

Each heading (``#``, ``##``, etc.) starts a new chunk.  Adjacent chunks
that are too small are merged.
"""

import re
from typing import List, Tuple

from src.constants import DEFAULT_CHUNK_SIZE
from src.schemas import ParsedDocument
from src.chunking.chunk_models import ChunkResult


def _split_by_headers(text: str) -> List[Tuple[str, str, int]]:
    """Split markdown into (heading, body, line_number) sections."""
    sections: List[Tuple[str, str, int]] = []
    current_heading = ""
    current_lines: List[str] = []
    heading_line = 1

    for line_no, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^#{1,6}\s", line):
            if current_heading or current_lines:
                body = "\n".join(current_lines).strip()
                sections.append((current_heading, body, heading_line))

            current_heading = line.strip()
            current_lines = []
            heading_line = line_no
        else:
            current_lines.append(line)

    if current_heading or current_lines:
        body = "\n".join(current_lines).strip()
        sections.append((current_heading, body, heading_line))

    return sections


def _merge_small_sections(
    sections: List[Tuple[str, str, int]],
    min_size: int = 100,
) -> List[Tuple[str, str, int]]:
    """Merge consecutive sections whose combined size is below *min_size*."""
    if not sections:
        return sections

    merged: List[Tuple[str, str, int]] = [sections[0]]

    for heading, body, line_no in sections[1:]:
        prev_heading, prev_body, prev_line = merged[-1]
        prev_text = f"{prev_heading}\n{prev_body}".strip()

        if len(prev_text) < min_size:
            combined_body = f"{prev_body}\n\n{heading}\n{body}".strip()
            merged[-1] = (prev_heading, combined_body, prev_line)
        else:
            merged.append((heading, body, line_no))

    return merged


def chunk_markdown(
    doc: ParsedDocument,
    min_section_size: int = 100,
) -> List[ChunkResult]:
    """
    Split a markdown document into chunks by heading structure.

    Small sections are merged with their neighbours.
    """
    sections = _split_by_headers(doc.source_code)
    sections = _merge_small_sections(sections, min_section_size)

    results: List[ChunkResult] = []

    for heading, body, line_no in sections:
        content = f"{heading}\n{body}".strip() if heading else body.strip()
        if not content:
            continue

        preamble = f"File: {doc.relative_path}\nSection: {heading or '(top)'}\n\n"
        text = preamble + content

        results.append(
            ChunkResult(
                text=text,
                content=content,
                symbol_name=heading.lstrip("#").strip() if heading else None,
                start_line=line_no,
                extra_metadata={"heading": heading},
            )
        )

    return results
