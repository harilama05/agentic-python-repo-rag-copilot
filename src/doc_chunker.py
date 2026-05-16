import hashlib
from pathlib import Path
from typing import List, Optional

from src.chunker import CodeChunk
from src.config import IGNORE_DIRS


DOC_EXTENSIONS = {".md", ".markdown"}


def should_ignore_path(path: Path) -> bool:
    parts = set(path.parts)

    for ignored_dir in IGNORE_DIRS:
        if ignored_dir in parts:
            return True

    return False


def scan_markdown_files(repo_path: str | Path) -> List[Path]:
    """
    Scan README.md and docs/*.md files in a repository.
    """
    repo_path = Path(repo_path).resolve()

    markdown_files: List[Path] = []

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue

        if should_ignore_path(path):
            continue

        if path.suffix.lower() not in DOC_EXTENSIONS:
            continue

        # Include README anywhere, and markdown docs in docs/ folders.
        name_lower = path.name.lower()
        parts_lower = {part.lower() for part in path.parts}

        if name_lower.startswith("readme") or "docs" in parts_lower:
            markdown_files.append(path)

    return sorted(markdown_files)


def _make_doc_chunk_id(
    file_path: str,
    heading: str,
    start_line: int,
    end_line: int,
) -> str:
    raw = f"doc:{file_path}:{heading}:{start_line}:{end_line}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _extract_heading(line: str) -> Optional[str]:
    stripped = line.strip()

    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()

    return None


def _build_doc_chunk_text(
    relative_path: str,
    heading: str,
    start_line: int,
    end_line: int,
    content: str,
) -> str:
    return "\n".join(
        [
            f"File: {relative_path}",
            f"Source type: documentation",
            f"Heading: {heading}",
            f"Lines: {start_line}-{end_line}",
            "",
            "Content:",
            content,
        ]
    )


def build_markdown_chunks(
    file_path: str | Path,
    repo_root: str | Path,
    max_lines_per_chunk: int = 40,
) -> List[CodeChunk]:
    """
    Build documentation chunks from README.md or docs/*.md.

    Chunking strategy:
    - split by markdown headings
    - if a section is too long, split by max_lines_per_chunk
    """
    file_path = Path(file_path).resolve()
    repo_root = Path(repo_root).resolve()

    try:
        relative_path = str(file_path.relative_to(repo_root))
    except ValueError:
        relative_path = str(file_path)

    relative_path = relative_path.replace("\\", "/")

    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    if not lines:
        return []

    sections = []

    current_heading = file_path.name
    current_start = 1
    current_lines = []

    for line_number, line in enumerate(lines, start=1):
        heading = _extract_heading(line)

        if heading and current_lines:
            sections.append(
                {
                    "heading": current_heading,
                    "start_line": current_start,
                    "end_line": line_number - 1,
                    "lines": current_lines,
                }
            )

            current_heading = heading
            current_start = line_number
            current_lines = [line]

        else:
            if heading:
                current_heading = heading
                current_start = line_number

            current_lines.append(line)

    if current_lines:
        sections.append(
            {
                "heading": current_heading,
                "start_line": current_start,
                "end_line": len(lines),
                "lines": current_lines,
            }
        )

    chunks: List[CodeChunk] = []

    for section in sections:
        section_lines = section["lines"]
        section_start = section["start_line"]
        heading = section["heading"]

        for offset in range(0, len(section_lines), max_lines_per_chunk):
            part_lines = section_lines[offset : offset + max_lines_per_chunk]

            start_line = section_start + offset
            end_line = start_line + len(part_lines) - 1

            content = "\n".join(part_lines)

            chunk_id = _make_doc_chunk_id(
                file_path=str(file_path),
                heading=heading,
                start_line=start_line,
                end_line=end_line,
            )

            text = _build_doc_chunk_text(
                relative_path=relative_path,
                heading=heading,
                start_line=start_line,
                end_line=end_line,
                content=content,
            )

            metadata = {
                "chunk_id": chunk_id,
                "source_type": "doc",
                "file_path": str(file_path),
                "relative_path": relative_path,
                "symbol_name": heading,
                "qualified_name": heading,
                "symbol_type": "documentation",
                "heading": heading,
                "start_line": start_line,
                "end_line": end_line,
                "parent": "",
                "docstring": "",
            }

            chunks.append(
                CodeChunk(
                    chunk_id=chunk_id,
                    text=text,
                    code=content,
                    metadata=metadata,
                )
            )

    return chunks