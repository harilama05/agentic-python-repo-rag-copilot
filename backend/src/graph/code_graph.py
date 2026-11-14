"""AST-based code graph construction and traversal utilities.

Static candidate relationships and optional runtime observations share stable
node IDs. Evidence and unresolved calls are retained across metadata storage.
"""

import ast
from dataclasses import asdict, dataclass, field
from collections import deque
from pathlib import Path
from typing import Dict, List, Set

from src.ingestion.scanner import scan_python_files


@dataclass
class CodeNode:
    """One function, class, or method in the repository graph."""

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
    """One relationship between two graph nodes."""

    source_id: str
    target_id: str
    edge_type: str
    certainty: str = "legacy_unknown"
    sites: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)


@dataclass
class ParsedDefinition:
    """Compatibility export for callers of the previous graph builder."""

    node: CodeNode
    ast_node: ast.AST
    class_name: str | None = None


class CodeGraph:
    """In-memory graph used for graph-aware repository analysis."""

    def __init__(self):
        self.nodes: Dict[str, CodeNode] = {}
        self.edges: List[CodeEdge] = []
        self.outgoing: Dict[str, List[CodeEdge]] = {}
        self.incoming: Dict[str, List[CodeEdge]] = {}
        self.name_to_ids: Dict[str, List[str]] = {}
        self.qualified_name_to_id: Dict[str, str] = {}
        self.unresolved_calls: list[dict] = []
        self.diagnostics: list[dict] = []
        self.node_info: dict[str, dict] = {}
        self.source_hashes: dict[str, str] = {}
        self.runtime_runs: list[dict] = []
        self.analysis_version = 0
        self._edge_index: dict[tuple[str, str, str], CodeEdge] = {}

    def add_node(self, node: CodeNode) -> None:
        """Add a graph node and update lookup indexes."""
        self.nodes[node.node_id] = node
        self.name_to_ids.setdefault(node.name, []).append(node.node_id)
        self.qualified_name_to_id[node.qualified_name] = node.node_id

    def add_edge(self, source_id: str, target_id: str, edge_type: str,
                 certainty: str = "legacy_unknown", sites: list[dict] | None = None,
                 observations: list[dict] | None = None) -> None:
        """Merge call sites; recursion is a valid relationship."""
        edge = CodeEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            certainty=certainty, sites=sites or [], observations=observations or [],
        )

        key = (source_id, target_id, edge_type)
        existing = self._edge_index.get(key)
        if existing is not None:
            for site in edge.sites:
                if site not in existing.sites:
                    existing.sites.append(site)
            for observation in edge.observations:
                if observation not in existing.observations:
                    existing.observations.append(observation)
            if existing.certainty == "legacy_unknown" or certainty == "inferred":
                existing.certainty = certainty
            return

        self._edge_index[key] = edge
        self.edges.append(edge)
        self.outgoing.setdefault(source_id, []).append(edge)
        self.incoming.setdefault(target_id, []).append(edge)

    def find_nodes(self, symbol: str) -> List[CodeNode]:
        """Find graph nodes by exact or suffix-qualified symbol matching."""
        symbol = symbol.strip()

        if not symbol:
            return []

        if symbol in self.nodes:
            return [self.nodes[symbol]]

        results: List[CodeNode] = []

        exact = [node for node in self.nodes.values() if node.qualified_name == symbol]
        if exact:
            return exact

        if symbol in self.name_to_ids:
            for node_id in self.name_to_ids[symbol]:
                results.append(self.nodes[node_id])

        for node in self.nodes.values():
            if node.qualified_name.endswith(f".{symbol}") and node not in results:
                results.append(node)

        return results

    def find_callers(self, symbol: str) -> Dict[str, List[CodeNode]]:
        """Find graph nodes that call the target symbol."""
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

    def call_edges(self, evidence: str = "all") -> list[CodeEdge]:
        if evidence not in {"all", "static", "observed"}:
            raise ValueError("evidence must be all, static, or observed")
        return [edge for edge in self.edges if edge.edge_type == "calls"
                and (evidence == "all" or (evidence == "observed" and edge.observations)
                     or (evidence == "static" and (edge.sites or edge.certainty == "legacy_unknown")))]

    def find_callees(self, symbol: str) -> Dict[str, List[CodeNode]]:
        """Find graph nodes called by the source symbol."""
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
        """Find nodes that may be affected if the target symbol changes."""
        target_nodes = self.find_nodes(symbol)
        visited: Set[str] = set()
        affected_ids: Set[str] = set()

        target_ids = {node.node_id for node in target_nodes}
        queue = deque([
            (node.node_id, 0)
            for node in target_nodes
        ])

        while queue:
            current_id, depth = queue.popleft()

            if current_id in visited:
                continue

            visited.add(current_id)

            if depth >= max_depth:
                continue

            for edge in self.incoming.get(current_id, []):
                if edge.edge_type != "calls":
                    continue

                caller_id = edge.source_id
                if caller_id not in target_ids:
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

    def analysis_snapshot(self) -> dict:
        """JSON sidecar preserves evidence without altering legacy edge columns."""
        return {"version": self.analysis_version, "edges": [asdict(e) for e in self.edges],
                "unresolved_calls": self.unresolved_calls, "diagnostics": self.diagnostics,
                "node_info": self.node_info, "source_hashes": self.source_hashes,
                "runtime_runs": self.runtime_runs}

    def restore_analysis(self, snapshot: dict) -> None:
        self.analysis_version = snapshot.get("version", 0)
        for key in ("unresolved_calls", "diagnostics", "runtime_runs"):
            setattr(self, key, snapshot.get(key, []))
        self.node_info = snapshot.get("node_info", {})
        self.source_hashes = snapshot.get("source_hashes", {})
        for item in snapshot.get("edges", []):
            if item["source_id"] in self.nodes and item["target_id"] in self.nodes:
                self.add_edge(**item)


def build_code_graph(repo_path: str | Path) -> CodeGraph:
    """Build scoped static relationships without importing/executing the repo."""
    from src.graph.static_analysis import build_from_sources
    root = Path(repo_path).resolve()
    sources = {path.resolve().relative_to(root).as_posix():
               path.read_text(encoding="utf-8", errors="replace")
               for path in scan_python_files(root)}
    return build_from_sources(sources)
