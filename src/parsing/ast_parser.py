"""
Python AST parser — extracts functions, classes, methods, imports, and
decorators from a ``.py`` file using the standard library ``ast`` module.
"""

import ast
from pathlib import Path
from typing import List, Optional

from src.schemas import CodeImport, CodeSymbol, FileType, ParsedDocument, SymbolType


def _get_end_line(node: ast.AST) -> int:
    return getattr(node, "end_lineno", getattr(node, "lineno", 0))


def _get_decorators(node: ast.AST) -> List[str]:
    """Extract decorator names from a function/class definition."""
    decorators: List[str] = []
    for dec in getattr(node, "decorator_list", []):
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(ast.dump(dec))
        elif isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name):
                decorators.append(func.id)
            elif isinstance(func, ast.Attribute):
                decorators.append(func.attr)
    return decorators


def _get_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """Extract parameter names from a function definition."""
    params: List[str] = []
    for arg in node.args.args:
        params.append(arg.arg)
    return params


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
    file_path: str,
    symbol_type: SymbolType,
    qualified_name: str,
    parent: Optional[str] = None,
) -> CodeSymbol:
    name = getattr(node, "name", "")
    decorators = _get_decorators(node)
    parameters = (
        _get_parameters(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        else []
    )

    return CodeSymbol(
        name=name,
        qualified_name=qualified_name,
        symbol_type=symbol_type,
        file_path=file_path,
        start_line=getattr(node, "lineno", 0),
        end_line=_get_end_line(node),
        docstring=ast.get_docstring(node),
        parent=parent,
        decorators=decorators,
        parameters=parameters,
    )


def _extract_symbols(tree: ast.AST, file_path: str) -> List[CodeSymbol]:
    symbols: List[CodeSymbol] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            symbols.append(
                _symbol_from_node(node, file_path, SymbolType.FUNCTION, node.name)
            )

        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                _symbol_from_node(node, file_path, SymbolType.ASYNC_FUNCTION, node.name)
            )

        elif isinstance(node, ast.ClassDef):
            class_name = node.name
            symbols.append(
                _symbol_from_node(node, file_path, SymbolType.CLASS, class_name)
            )

            # Extract methods inside class
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    symbols.append(
                        _symbol_from_node(
                            child,
                            file_path,
                            SymbolType.METHOD,
                            f"{class_name}.{child.name}",
                            parent=class_name,
                        )
                    )
                elif isinstance(child, ast.AsyncFunctionDef):
                    symbols.append(
                        _symbol_from_node(
                            child,
                            file_path,
                            SymbolType.ASYNC_METHOD,
                            f"{class_name}.{child.name}",
                            parent=class_name,
                        )
                    )

    return symbols


def parse_python_file(
    file_path: str | Path,
    relative_path: Optional[str] = None,
) -> ParsedDocument:
    """
    Parse a Python file using the ``ast`` module.

    Returns a ``ParsedDocument`` with extracted symbols and imports.
    """
    file_path = Path(file_path).resolve()
    source_code = file_path.read_text(encoding="utf-8", errors="ignore")

    rel = relative_path or str(file_path)

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return ParsedDocument(
            file_path=str(file_path),
            relative_path=rel,
            file_type=FileType.PYTHON,
            source_code=source_code,
            imports=[],
            symbols=[],
            syntax_error=str(exc),
        )

    imports = _extract_imports(tree)
    symbols = _extract_symbols(tree, str(file_path))

    return ParsedDocument(
        file_path=str(file_path),
        relative_path=rel,
        file_type=FileType.PYTHON,
        source_code=source_code,
        imports=imports,
        symbols=symbols,
        syntax_error=None,
    )
