"""
Lightweight AST code graph for relationship-aware code retrieval.

The graph is intentionally kept separate from hybrid retrieval. Vector, BM25,
and symbol search still get fused by RRF; this graph is used only by agent tools
for relationship queries such as callers, callees, references, and impact.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.ingestion.scanner import scan_repository
from src.metadata.id_generator import generate_chunk_id


@dataclass
class CodeNode:
    node_id: str
    chunk_id: str
    name: str
    qualified_name: str
    node_type: str
    file_path: str
    relative_path: str
    start_line: int
    end_line: int
    parent: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeNode":
        return cls(**data)


@dataclass(frozen=True)
class CodeEdge:
    source_id: str
    target_id: str
    edge_type: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeEdge":
        return cls(**data)


@dataclass
class ParsedDefinition:
    node: CodeNode
    ast_node: ast.AST
    class_name: Optional[str] = None


class CodeGraph:
    def __init__(self):
        self.nodes: Dict[str, CodeNode] = {}
        self.edges: List[CodeEdge] = []
        self.outgoing: Dict[str, List[CodeEdge]] = {}
        self.incoming: Dict[str, List[CodeEdge]] = {}
        self.name_to_ids: Dict[str, List[str]] = {}
        self.qualified_name_to_id: Dict[str, str] = {}
        self._edge_keys: Set[Tuple[str, str, str]] = set()

    def add_node(self, node: CodeNode) -> None:
        self.nodes[node.node_id] = node
        self.name_to_ids.setdefault(node.name, [])
        if node.node_id not in self.name_to_ids[node.name]:
            self.name_to_ids[node.name].append(node.node_id)
        self.qualified_name_to_id[node.qualified_name] = node.node_id

    def add_edge(self, source_id: str, target_id: str, edge_type: str) -> None:
        if source_id == target_id:
            return

        key = (source_id, target_id, edge_type)
        if key in self._edge_keys:
            return

        edge = CodeEdge(source_id=source_id, target_id=target_id, edge_type=edge_type)
        self._edge_keys.add(key)
        self.edges.append(edge)
        self.outgoing.setdefault(source_id, []).append(edge)
        self.incoming.setdefault(target_id, []).append(edge)

    def find_nodes(self, symbol: str) -> List[CodeNode]:
        symbol = symbol.strip()
        if not symbol:
            return []

        if symbol in self.qualified_name_to_id:
            return [self.nodes[self.qualified_name_to_id[symbol]]]

        results: List[CodeNode] = []
        seen: Set[str] = set()

        for node_id in self.name_to_ids.get(symbol, []):
            results.append(self.nodes[node_id])
            seen.add(node_id)

        for node in self.nodes.values():
            if node.node_id not in seen and node.qualified_name.endswith(symbol):
                results.append(node)
                seen.add(node.node_id)

        return results

    def find_callers(self, symbol: str) -> Dict[str, List[CodeNode]]:
        targets = self.find_nodes(symbol)
        caller_ids: Set[str] = set()

        for target in targets:
            for edge in self.incoming.get(target.node_id, []):
                if edge.edge_type == "calls":
                    caller_ids.add(edge.source_id)

        return {
            "targets": targets,
            "callers": [self.nodes[node_id] for node_id in sorted(caller_ids)],
        }

    def find_callees(self, symbol: str) -> Dict[str, List[CodeNode]]:
        sources = self.find_nodes(symbol)
        callee_ids: Set[str] = set()

        for source in sources:
            for edge in self.outgoing.get(source.node_id, []):
                if edge.edge_type == "calls":
                    callee_ids.add(edge.target_id)

        return {
            "sources": sources,
            "callees": [self.nodes[node_id] for node_id in sorted(callee_ids)],
        }

    def impact_analysis(self, symbol: str, max_depth: int = 2) -> Dict[str, List[CodeNode]]:
        targets = self.find_nodes(symbol)
        visited: Set[str] = set()
        affected_ids: Set[str] = set()
        queue: List[Tuple[str, int]] = [(node.node_id, 0) for node in targets]

        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            if depth >= max_depth:
                continue

            for edge in self.incoming.get(current_id, []):
                if edge.edge_type != "calls":
                    continue
                affected_ids.add(edge.source_id)
                queue.append((edge.source_id, depth + 1))

        return {
            "targets": targets,
            "affected": [self.nodes[node_id] for node_id in sorted(affected_ids)],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeGraph":
        graph = cls()
        for node_data in data.get("nodes", {}).values():
            graph.add_node(CodeNode.from_dict(node_data))
        for edge_data in data.get("edges", []):
            edge = CodeEdge.from_dict(edge_data)
            graph.add_edge(edge.source_id, edge.target_id, edge.edge_type)
        return graph


def _get_end_line(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))


def _make_node(
    file_path: Path,
    relative_path: str,
    name: str,
    qualified_name: str,
    node_type: str,
    start_line: int,
    end_line: int,
    parent: str = "",
) -> CodeNode:
    file_path_str = str(file_path.resolve())
    chunk_id = generate_chunk_id(
        file_path=file_path_str,
        qualified_name=qualified_name,
        start_line=start_line,
        end_line=end_line,
    )
    return CodeNode(
        node_id=chunk_id,
        chunk_id=chunk_id,
        name=name,
        qualified_name=qualified_name,
        node_type=node_type,
        file_path=file_path_str,
        relative_path=relative_path,
        start_line=start_line,
        end_line=end_line,
        parent=parent,
    )


def _collect_definitions_for_file(file_path: Path, repo_root: Path) -> List[ParsedDefinition]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)
    relative_path = str(file_path.resolve().relative_to(repo_root)).replace("\\", "/")
    definitions: List[ParsedDefinition] = []

    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node = _make_node(
                file_path=file_path,
                relative_path=relative_path,
                name=item.name,
                qualified_name=item.name,
                node_type="async_function" if isinstance(item, ast.AsyncFunctionDef) else "function",
                start_line=item.lineno,
                end_line=_get_end_line(item),
            )
            definitions.append(ParsedDefinition(node=node, ast_node=item))

        elif isinstance(item, ast.ClassDef):
            class_node = _make_node(
                file_path=file_path,
                relative_path=relative_path,
                name=item.name,
                qualified_name=item.name,
                node_type="class",
                start_line=item.lineno,
                end_line=_get_end_line(item),
            )
            definitions.append(ParsedDefinition(node=class_node, ast_node=item))

            for child in item.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                qualified_name = f"{item.name}.{child.name}"
                method_node = _make_node(
                    file_path=file_path,
                    relative_path=relative_path,
                    name=child.name,
                    qualified_name=qualified_name,
                    node_type="async_method"
                    if isinstance(child, ast.AsyncFunctionDef)
                    else "method",
                    start_line=child.lineno,
                    end_line=_get_end_line(child),
                    parent=item.name,
                )
                definitions.append(
                    ParsedDefinition(
                        node=method_node,
                        ast_node=child,
                        class_name=item.name,
                    )
                )

    return definitions


def _get_name_from_call_func(func: ast.AST) -> Optional[str]:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _collect_local_instance_types(
    function_node: ast.AST,
    class_names: Set[str],
) -> Dict[str, str]:
    local_types: Dict[str, str] = {}

    for node in ast.walk(function_node):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue

        class_name = _get_name_from_call_func(node.value.func)
        if class_name not in class_names:
            continue

        for target in node.targets:
            if isinstance(target, ast.Name):
                local_types[target.id] = class_name

    return local_types


def _resolve_call_symbol(
    func: ast.AST,
    local_types: Dict[str, str],
    current_class: Optional[str],
) -> Optional[str]:
    if isinstance(func, ast.Name):
        return func.id

    if isinstance(func, ast.Attribute):
        attr = func.attr
        if isinstance(func.value, ast.Name):
            object_name = func.value.id
            if object_name in local_types:
                return f"{local_types[object_name]}.{attr}"
            if object_name == "self" and current_class:
                return f"{current_class}.{attr}"
        return attr

    return None


def _resolve_target_node_ids(graph: CodeGraph, call_symbol: str) -> List[str]:
    if call_symbol in graph.qualified_name_to_id:
        return [graph.qualified_name_to_id[call_symbol]]
    if call_symbol in graph.name_to_ids:
        return graph.name_to_ids[call_symbol]

    return [
        node.node_id
        for node in graph.nodes.values()
        if node.qualified_name.endswith(call_symbol)
    ]


def build_code_graph(repo_path: str | Path) -> CodeGraph:
    repo_root = Path(repo_path).resolve()
    python_files = [path for path in scan_repository(repo_root) if path.suffix == ".py"]

    graph = CodeGraph()
    all_definitions: List[ParsedDefinition] = []

    for file_path in python_files:
        try:
            definitions = _collect_definitions_for_file(file_path, repo_root)
        except SyntaxError:
            continue

        for definition in definitions:
            graph.add_node(definition.node)
        all_definitions.extend(definitions)

    for definition in all_definitions:
        node = definition.node
        if not node.parent:
            continue

        for parent in graph.find_nodes(node.parent):
            if parent.relative_path == node.relative_path and parent.node_type == "class":
                graph.add_edge(parent.node_id, node.node_id, "contains")

    class_names = {
        node.name for node in graph.nodes.values() if node.node_type == "class"
    }

    for definition in all_definitions:
        source = definition.node
        if source.node_type not in {"function", "async_function", "method", "async_method"}:
            continue

        local_types = _collect_local_instance_types(definition.ast_node, class_names)

        for ast_node in ast.walk(definition.ast_node):
            if not isinstance(ast_node, ast.Call):
                continue

            call_symbol = _resolve_call_symbol(
                func=ast_node.func,
                local_types=local_types,
                current_class=definition.class_name,
            )
            if not call_symbol:
                continue

            for target_id in _resolve_target_node_ids(graph, call_symbol):
                graph.add_edge(source.node_id, target_id, "calls")

    return graph
