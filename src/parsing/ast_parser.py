"""Python AST parsing utilities for repository indexing.

This module extracts imports and top-level symbols from Python files so the
chunking and graph-building layers can work with normalized structures.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CodeImport:
    """One import statement extracted from a Python file."""

    module: Optional[str]
    name: str
    alias: Optional[str]
    line: int


@dataclass
class CodeSymbol:
    """One function, async function, class, or method extracted from a file."""

    name: str
    qualified_name: str
    symbol_type: str
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    parent: Optional[str] = None


@dataclass
class ParsedPythonFile:
    """Normalized parsed representation of a Python source file."""

    file_path: str
    source_code: str
    imports: List[CodeImport]
    symbols: List[CodeSymbol]
    syntax_error: Optional[str] = None


def _get_end_line(node: ast.AST) -> int:
    return getattr(node, "end_lineno", getattr(node, "lineno", 0))


def _extract_imports(tree: ast.AST) -> List[CodeImport]:
    imports: List[CodeImport] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    CodeImport(
                        module=None,
                        name=alias.name,
                        alias=alias.asname,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for alias in node.names:
                imports.append(
                    CodeImport(
                        module=module,
                        name=alias.name,
                        alias=alias.asname,
                        line=node.lineno,
                    )
                )

    return imports


def _symbol_from_node(
    node: ast.AST,
    file_path: Path,
    symbol_type: str,
    qualified_name: str,
    parent: Optional[str] = None,
) -> CodeSymbol:
    name = getattr(node, "name")

    return CodeSymbol(
        name=name,
        qualified_name=qualified_name,
        symbol_type=symbol_type,
        file_path=str(file_path),
        start_line=getattr(node, "lineno", 0),
        end_line=_get_end_line(node),
        docstring=ast.get_docstring(node),
        parent=parent,
    )


def _extract_symbols(tree: ast.AST, file_path: Path) -> List[CodeSymbol]:
    symbols: List[CodeSymbol] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            symbols.append(
                _symbol_from_node(
                    node=node,
                    file_path=file_path,
                    symbol_type="function",
                    qualified_name=node.name,
                )
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                _symbol_from_node(
                    node=node,
                    file_path=file_path,
                    symbol_type="async_function",
                    qualified_name=node.name,
                )
            )
        elif isinstance(node, ast.ClassDef):
            class_name = node.name

            symbols.append(
                _symbol_from_node(
                    node=node,
                    file_path=file_path,
                    symbol_type="class",
                    qualified_name=class_name,
                )
            )

            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    symbols.append(
                        _symbol_from_node(
                            node=child,
                            file_path=file_path,
                            symbol_type="method",
                            qualified_name=f"{class_name}.{child.name}",
                            parent=class_name,
                        )
                    )
                elif isinstance(child, ast.AsyncFunctionDef):
                    symbols.append(
                        _symbol_from_node(
                            node=child,
                            file_path=file_path,
                            symbol_type="async_method",
                            qualified_name=f"{class_name}.{child.name}",
                            parent=class_name,
                        )
                    )

    return symbols


def parse_python_file(file_path: str | Path) -> ParsedPythonFile:
    """Parse one Python file into imports and symbols."""
    file_path = Path(file_path).resolve()
    source_code = file_path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return ParsedPythonFile(
            file_path=str(file_path),
            source_code=source_code,
            imports=[],
            symbols=[],
            syntax_error=str(exc),
        )

    imports = _extract_imports(tree)
    symbols = _extract_symbols(tree, file_path)

    return ParsedPythonFile(
        file_path=str(file_path),
        source_code=source_code,
        imports=imports,
        symbols=symbols,
        syntax_error=None,
    )
