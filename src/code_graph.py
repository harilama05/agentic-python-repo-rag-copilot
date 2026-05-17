import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.scanner import scan_python_files


@dataclass
class CodeNode:
    node_id: str
    name: str
    qualified_name: str
    node_type: str
    relative_path: str
    start_line: int
    end_line: int
    parent: str = ""


@dataclass
class CodeEdge:
    source_id: str
    target_id: str
    edge_type: str


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

    def add_node(self, node: CodeNode) -> None:
        self.nodes[node.node_id] = node
        self.name_to_ids.setdefault(node.name, []).append(node.node_id)
        self.qualified_name_to_id[node.qualified_name] = node.node_id

    def add_edge(self, source_id: str, target_id: str, edge_type: str) -> None:
        if source_id == target_id:
            return

        edge = CodeEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
        )

        # Avoid duplicate edges.
        for existing in self.edges:
            if (
                existing.source_id == edge.source_id
                and existing.target_id == edge.target_id
                and existing.edge_type == edge.edge_type
            ):
                return

        self.edges.append(edge)
        self.outgoing.setdefault(source_id, []).append(edge)
        self.incoming.setdefault(target_id, []).append(edge)

    def find_nodes(self, symbol: str) -> List[CodeNode]:
        symbol = symbol.strip()

        if not symbol:
            return []

        results: List[CodeNode] = []

        # Exact qualified name match.
        if symbol in self.qualified_name_to_id:
            node_id = self.qualified_name_to_id[symbol]
            return [self.nodes[node_id]]

        # Exact simple name match.
        if symbol in self.name_to_ids:
            for node_id in self.name_to_ids[symbol]:
                results.append(self.nodes[node_id])

        # Suffix qualified match, e.g. "TaskService.create_task".
        for node in self.nodes.values():
            if node.qualified_name.endswith(symbol) and node not in results:
                results.append(node)

        return results

    def find_callers(self, symbol: str) -> Dict[str, List[CodeNode]]:
        target_nodes = self.find_nodes(symbol)
        caller_ids: Set[str] = set()

        for target in target_nodes:
            for edge in self.incoming.get(target.node_id, []):
                if edge.edge_type == "calls":
                    caller_ids.add(edge.source_id)

        callers = [self.nodes[node_id] for node_id in sorted(caller_ids)]

        return {
            "targets": target_nodes,
            "callers": callers,
        }

    def find_callees(self, symbol: str) -> Dict[str, List[CodeNode]]:
        source_nodes = self.find_nodes(symbol)
        callee_ids: Set[str] = set()

        for source in source_nodes:
            for edge in self.outgoing.get(source.node_id, []):
                if edge.edge_type == "calls":
                    callee_ids.add(edge.target_id)

        callees = [self.nodes[node_id] for node_id in sorted(callee_ids)]

        return {
            "sources": source_nodes,
            "callees": callees,
        }

    def impact_analysis(self, symbol: str, max_depth: int = 2) -> Dict[str, List[CodeNode]]:
        """
        Find code nodes that may be affected if a symbol changes or is removed.

        Current strategy:
        - find target symbol nodes
        - traverse incoming call edges backward
        - return direct and indirect callers up to max_depth
        """
        target_nodes = self.find_nodes(symbol)
        visited: Set[str] = set()
        affected_ids: Set[str] = set()

        queue: List[Tuple[str, int]] = [
            (node.node_id, 0)
            for node in target_nodes
        ]

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

                caller_id = edge.source_id
                affected_ids.add(caller_id)
                queue.append((caller_id, depth + 1))

        affected_nodes = [
            self.nodes[node_id]
            for node_id in sorted(affected_ids)
        ]

        return {
            "targets": target_nodes,
            "affected": affected_nodes,
        }


def _node_id(relative_path: str, qualified_name: str, start_line: int, end_line: int) -> str:
    return f"{relative_path}:{qualified_name}:{start_line}-{end_line}"


def _get_end_line(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))


def _collect_definitions_for_file(
    file_path: Path,
    repo_root: Path,
) -> List[ParsedDefinition]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)

    relative_path = str(file_path.resolve().relative_to(repo_root)).replace("\\", "/")

    definitions: List[ParsedDefinition] = []

    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = item.lineno
            end_line = _get_end_line(item)
            qualified_name = item.name

            node = CodeNode(
                node_id=_node_id(relative_path, qualified_name, start_line, end_line),
                name=item.name,
                qualified_name=qualified_name,
                node_type="function",
                relative_path=relative_path,
                start_line=start_line,
                end_line=end_line,
            )

            definitions.append(
                ParsedDefinition(
                    node=node,
                    ast_node=item,
                    class_name=None,
                )
            )

        elif isinstance(item, ast.ClassDef):
            class_start = item.lineno
            class_end = _get_end_line(item)

            class_node = CodeNode(
                node_id=_node_id(relative_path, item.name, class_start, class_end),
                name=item.name,
                qualified_name=item.name,
                node_type="class",
                relative_path=relative_path,
                start_line=class_start,
                end_line=class_end,
            )

            definitions.append(
                ParsedDefinition(
                    node=class_node,
                    ast_node=item,
                    class_name=None,
                )
            )

            for child in item.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start_line = child.lineno
                    end_line = _get_end_line(child)
                    qualified_name = f"{item.name}.{child.name}"

                    method_node = CodeNode(
                        node_id=_node_id(relative_path, qualified_name, start_line, end_line),
                        name=child.name,
                        qualified_name=qualified_name,
                        node_type="method",
                        relative_path=relative_path,
                        start_line=start_line,
                        end_line=end_line,
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
    """
    Detect simple local variable assignments like:

    service = TaskService()

    Then we can resolve:

    service.create_task() -> TaskService.create_task
    """
    local_types: Dict[str, str] = {}

    for node in ast.walk(function_node):
        if not isinstance(node, ast.Assign):
            continue

        if not isinstance(node.value, ast.Call):
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

        # service.create_task() where service = TaskService()
        if isinstance(func.value, ast.Name):
            object_name = func.value.id

            if object_name in local_types:
                return f"{local_types[object_name]}.{attr}"

            # self.method() inside class.
            if object_name == "self" and current_class:
                return f"{current_class}.{attr}"

        # Fallback: use method/function name only.
        return attr

    return None


def _resolve_target_node_ids(
    graph: CodeGraph,
    call_symbol: str,
) -> List[str]:
    # Exact qualified match.
    if call_symbol in graph.qualified_name_to_id:
        return [graph.qualified_name_to_id[call_symbol]]

    # Exact simple name match.
    if call_symbol in graph.name_to_ids:
        return graph.name_to_ids[call_symbol]

    # Suffix match.
    matches = []

    for node in graph.nodes.values():
        if node.qualified_name.endswith(call_symbol):
            matches.append(node.node_id)

    return matches


def build_code_graph(repo_path: str | Path) -> CodeGraph:
    """
    Build a lightweight Python code graph from AST.

    Nodes:
    - functions
    - classes
    - methods

    Edges:
    - contains
    - calls
    """
    repo_root = Path(repo_path).resolve()
    python_files = scan_python_files(repo_root)

    graph = CodeGraph()
    all_definitions: List[ParsedDefinition] = []

    # First pass: collect all nodes.
    for file_path in python_files:
        try:
            definitions = _collect_definitions_for_file(file_path, repo_root)
        except SyntaxError:
            continue

        for definition in definitions:
            graph.add_node(definition.node)

        all_definitions.extend(definitions)

    # Add class -> method contains edges.
    for definition in all_definitions:
        node = definition.node

        if not node.parent:
            continue

        parent_nodes = graph.find_nodes(node.parent)

        for parent in parent_nodes:
            if (
                parent.relative_path == node.relative_path
                and parent.node_type == "class"
            ):
                graph.add_edge(
                    source_id=parent.node_id,
                    target_id=node.node_id,
                    edge_type="contains",
                )

    class_names = {
        node.name
        for node in graph.nodes.values()
        if node.node_type == "class"
    }

    # Second pass: collect calls inside functions and methods.
    for definition in all_definitions:
        source_node = definition.node

        if source_node.node_type not in {"function", "method"}:
            continue

        function_node = definition.ast_node
        local_types = _collect_local_instance_types(
            function_node=function_node,
            class_names=class_names,
        )

        for ast_node in ast.walk(function_node):
            if not isinstance(ast_node, ast.Call):
                continue

            call_symbol = _resolve_call_symbol(
                func=ast_node.func,
                local_types=local_types,
                current_class=definition.class_name,
            )

            if not call_symbol:
                continue

            target_node_ids = _resolve_target_node_ids(graph, call_symbol)

            for target_node_id in target_node_ids:
                graph.add_edge(
                    source_id=source_node.node_id,
                    target_id=target_node_id,
                    edge_type="calls",
                )

    return graph