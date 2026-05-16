"""
AST-based code chunker.

Each function, class, and method becomes one chunk. The chunk text includes
a metadata preamble (file path, symbol name, type, docstring, imports)
followed by the raw source code. This gives the embedding model rich
semantic context.
"""

from pathlib import Path
from typing import List, Optional

from src.schemas import ParsedDocument, CodeSymbol
from src.chunking.chunk_models import ChunkResult


def _extract_source_segment(source_code: str, start_line: int, end_line: int) -> str:
    """Extract lines from source; AST lines are 1-based."""
    lines = source_code.splitlines()
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    return "\n".join(lines[start_idx:end_idx])


def _format_imports(doc: ParsedDocument) -> str:
    if not doc.imports:
        return ""

    formatted = []
    for imp in doc.imports:
        if imp.module:
            line = f"from {imp.module} import {imp.name}"
        else:
            line = f"import {imp.name}"
        if imp.alias:
            line += f" as {imp.alias}"
        formatted.append(line)

    return "\n".join(formatted)


def _get_class_methods(doc: ParsedDocument, class_name: str) -> List[str]:
    return [s.qualified_name for s in doc.symbols if s.parent == class_name]


def _build_chunk_text(
    doc: ParsedDocument,
    symbol: CodeSymbol,
    code: str,
) -> str:
    """Build a rich text representation with metadata preamble."""
    parts = [
        f"File: {doc.relative_path}",
        f"Symbol: {symbol.qualified_name}",
        f"Type: {symbol.symbol_type.value}",
        f"Lines: {symbol.start_line}-{symbol.end_line}",
    ]

    if symbol.parent:
        parts.append(f"Parent class: {symbol.parent}")

    if symbol.decorators:
        parts.append(f"Decorators: {', '.join(symbol.decorators)}")

    if symbol.parameters:
        parts.append(f"Parameters: {', '.join(symbol.parameters)}")

    if symbol.docstring:
        parts.append(f"Docstring: {symbol.docstring}")

    if symbol.symbol_type.value == "class":
        methods = _get_class_methods(doc, symbol.name)
        if methods:
            parts.append("Methods: " + ", ".join(methods))

    imports_text = _format_imports(doc)
    if imports_text:
        parts.append("\nImports:\n" + imports_text)

    parts.append("\nCode:\n" + code)

    return "\n".join(parts)


def chunk_code(
    doc: ParsedDocument,
) -> List[ChunkResult]:
    """
    Create one ``ChunkResult`` per symbol (function / class / method).

    Files with syntax errors produce zero chunks.
    """
    if doc.syntax_error:
        return []

    chunks: List[ChunkResult] = []

    for symbol in doc.symbols:
        code = _extract_source_segment(
            doc.source_code, symbol.start_line, symbol.end_line
        )

        text = _build_chunk_text(doc, symbol, code)

        chunks.append(
            ChunkResult(
                text=text,
                content=code,
                symbol_name=symbol.name,
                qualified_name=symbol.qualified_name,
                symbol_type=symbol.symbol_type.value,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                parent=symbol.parent,
                docstring=symbol.docstring,
            )
        )

    return chunks
