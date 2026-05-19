"""Code chunking utilities for parsed Python files.

This module converts parsed symbols into chunk objects suitable for embedding,
retrieval, and metadata persistence.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.constants import SOURCE_TYPE_CODE
from src.parsing.ast_parser import CodeSymbol, ParsedPythonFile


@dataclass
class CodeChunk:
    """One code or documentation chunk prepared for indexing."""

    chunk_id: str
    text: str
    code: str
    metadata: Dict[str, Any]


def _make_chunk_id(file_path: str, qualified_name: str, start_line: int, end_line: int) -> str:
    raw = f"{file_path}:{qualified_name}:{start_line}:{end_line}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _extract_source_segment(source_code: str, start_line: int, end_line: int) -> str:
    lines = source_code.splitlines()
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    return "\n".join(lines[start_idx:end_idx])


def _format_imports(parsed_file: ParsedPythonFile) -> str:
    if not parsed_file.imports:
        return ""

    formatted_imports = []

    for imp in parsed_file.imports:
        if imp.module:
            line = f"from {imp.module} import {imp.name}"
        else:
            line = f"import {imp.name}"

        if imp.alias:
            line += f" as {imp.alias}"

        formatted_imports.append(line)

    return "\n".join(formatted_imports)


def _get_class_methods(parsed_file: ParsedPythonFile, class_name: str) -> List[str]:
    methods = []

    for symbol in parsed_file.symbols:
        if symbol.parent == class_name:
            methods.append(symbol.qualified_name)

    return methods


def _build_chunk_text(
    parsed_file: ParsedPythonFile,
    symbol: CodeSymbol,
    code: str,
    repo_root: Optional[Path] = None,
) -> str:
    file_path = Path(symbol.file_path)

    if repo_root:
        try:
            display_path = str(file_path.relative_to(repo_root))
        except ValueError:
            display_path = str(file_path)
    else:
        display_path = str(file_path)

    imports_text = _format_imports(parsed_file)

    parts = [
        f"File: {display_path}",
        f"Symbol: {symbol.qualified_name}",
        f"Type: {symbol.symbol_type}",
        f"Lines: {symbol.start_line}-{symbol.end_line}",
    ]

    if symbol.parent:
        parts.append(f"Parent class: {symbol.parent}")

    if symbol.docstring:
        parts.append(f"Docstring: {symbol.docstring}")

    if symbol.symbol_type == "class":
        methods = _get_class_methods(parsed_file, symbol.name)
        if methods:
            parts.append("Methods: " + ", ".join(methods))

    if imports_text:
        parts.append("\nImports:\n" + imports_text)

    parts.append("\nCode:\n" + code)
    return "\n".join(parts)


def build_code_chunks(
    parsed_file: ParsedPythonFile,
    repo_root: Optional[str | Path] = None,
) -> List[CodeChunk]:
    """Build code chunks from a parsed Python file."""
    if parsed_file.syntax_error:
        return []

    repo_root_path = Path(repo_root).resolve() if repo_root else None
    chunks: List[CodeChunk] = []

    for symbol in parsed_file.symbols:
        code = _extract_source_segment(
            source_code=parsed_file.source_code,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
        )

        chunk_id = _make_chunk_id(
            file_path=symbol.file_path,
            qualified_name=symbol.qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
        )

        file_path = Path(symbol.file_path)

        if repo_root_path:
            try:
                relative_path = str(file_path.relative_to(repo_root_path))
            except ValueError:
                relative_path = str(file_path)
        else:
            relative_path = str(file_path)

        text = _build_chunk_text(
            parsed_file=parsed_file,
            symbol=symbol,
            code=code,
            repo_root=repo_root_path,
        )

        metadata = {
            "chunk_id": chunk_id,
            "source_type": SOURCE_TYPE_CODE,
            "file_path": str(file_path),
            "relative_path": relative_path,
            "symbol_name": symbol.name,
            "qualified_name": symbol.qualified_name,
            "symbol_type": symbol.symbol_type,
            "start_line": symbol.start_line,
            "end_line": symbol.end_line,
            "parent": symbol.parent,
            "docstring": symbol.docstring,
        }

        chunks.append(
            CodeChunk(
                chunk_id=chunk_id,
                text=text,
                code=code,
                metadata=metadata,
            )
        )

    return chunks
