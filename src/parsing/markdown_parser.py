"""
Markdown parser — splits a Markdown document into sections by headings.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from src.schemas import FileType, ParsedDocument


def _split_by_headers(text: str) -> List[Tuple[str, str, int]]:
    """
    Split markdown text into (heading, body, line_number) tuples.

    Returns a list where each element is a section headed by a markdown
    heading (``# …``, ``## …``, etc.).
    """
    sections: List[Tuple[str, str, int]] = []
    current_heading = ""
    current_body_lines: List[str] = []
    heading_line = 1

    for line_no, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^#{1,6}\s", line):
            # Save previous section
            if current_heading or current_body_lines:
                body = "\n".join(current_body_lines).strip()
                sections.append((current_heading, body, heading_line))

            current_heading = line.strip()
            current_body_lines = []
            heading_line = line_no
        else:
            current_body_lines.append(line)

    # Last section
    if current_heading or current_body_lines:
        body = "\n".join(current_body_lines).strip()
        sections.append((current_heading, body, heading_line))

    return sections


def parse_markdown_file(
    file_path: str | Path,
    relative_path: Optional[str] = None,
) -> ParsedDocument:
    """
    Parse a Markdown file into a ``ParsedDocument``.

    Unlike Python parsing, markdown has no symbols/imports — the raw text
    and section structure will be used by the markdown chunker.
    """
    file_path = Path(file_path).resolve()
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    rel = relative_path or str(file_path)

    return ParsedDocument(
        file_path=str(file_path),
        relative_path=rel,
        file_type=FileType.MARKDOWN,
        source_code=source,
    )
