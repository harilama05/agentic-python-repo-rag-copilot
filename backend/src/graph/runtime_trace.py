"""Opt-in runtime evidence for trusted programs; never called by chat tools."""

import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.graph.code_graph import CodeGraph, build_code_graph
from src.graph.static_analysis import source_hash


class RuntimeCallRecorder:
    """Collect Python call events in the current thread, without recording locals."""

    def __init__(self, repo_root: str | Path, *, label: str = "manual run", max_events: int = 100000):
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self.root = Path(repo_root).resolve()
        self.graph = build_code_graph(self.root)
        self.label = label[:200]
        self.max_events = max_events
        self.events = Counter()
        self.nodes = set()
        self.seen_events = 0
        self.truncated = False
        self.cache = {}
        self.node_index = {}
        for node in self.graph.nodes.values():
            key = (node.relative_path, self.graph.node_info[node.node_id]["runtime_first_line"])
            if node.node_type != "class":
                self.node_index.setdefault(key, []).append(node)
        self.run_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc).isoformat()

    def locate(self, code):
        if code in self.cache:
            return self.cache[code]
        try:
            path = Path(code.co_filename).resolve().relative_to(self.root).as_posix()
        except (ValueError, OSError):
            self.cache[code] = None
            return None
        qualified = getattr(code, "co_qualname", "").replace(".<locals>.", ".")
        matches = [node for node in self.node_index.get((path, code.co_firstlineno), [])
                   if (node.qualified_name == qualified if qualified else node.name == code.co_name)]
        result = matches[0].node_id if len(matches) == 1 else None
        self.cache[code] = result
        return result

    def profile(self, frame, event, arg):
        if event != "call":
            return
        target = self.locate(frame.f_code)
        if target is None:
            return
        if self.seen_events >= self.max_events:
            self.truncated = True
            return
        self.seen_events += 1
        self.nodes.add(target)
        caller_frame = frame.f_back
        source = self.locate(caller_frame.f_code) if caller_frame else None
        if source is not None:
            self.events[(source, target, caller_frame.f_lineno)] += 1

    def __enter__(self):
        if sys.getprofile() is not None:
            raise RuntimeError("A profiler is already active; do not overwrite its hook")
        self.previous_profile = sys.getprofile()
        sys.setprofile(self.profile)
        return self

    def __exit__(self, exc_type, exc, traceback):
        sys.setprofile(self.previous_profile)
        clean_exit = exc_type is None or (isinstance(exc, SystemExit) and exc.code in (None, 0))
        self.exit_status = "completed" if clean_exit else "raised"

    def report(self) -> dict:
        after = {path: source_hash((self.root / path).read_text(encoding="utf-8", errors="replace"))
                 if (self.root / path).is_file() else None for path in self.graph.source_hashes}
        return {"version": 1, "run_id": self.run_id, "label": self.label,
                "created_at": self.created_at, "source_hashes": self.graph.source_hashes,
                "sources_unchanged": after == self.graph.source_hashes,
                "scope": "current_thread_python_call_events", "truncated": self.truncated,
                "exit_status": getattr(self, "exit_status", "unknown"),
                "observed_nodes": sorted(self.nodes), "call_events": self.seen_events,
                "edges": [{"source_id": source, "target_id": target, "line": line, "call_events": count}
                          for (source, target, line), count in sorted(self.events.items())]}


def apply_runtime_report(graph: CodeGraph, report: dict, source_files: dict[str, str]) -> dict:
    """Validate provenance before adding observational edges, including dynamic calls."""
    if not isinstance(report, dict) or report.get("version") != 1:
        raise ValueError("Unsupported runtime report format")
    if not isinstance(report.get("run_id"), str) or not 1 <= len(report["run_id"]) <= 100:
        raise ValueError("Runtime report needs a bounded run_id")
    if report.get("sources_unchanged") is not True:
        raise ValueError("Source changed during recording; record again")
    expected = {p.replace("\\", "/"): source_hash(text) for p, text in source_files.items() if p.endswith(".py")}
    if not graph.source_hashes or report.get("source_hashes") != graph.source_hashes or expected != graph.source_hashes:
        raise ValueError("Runtime report does not match the indexed source version; refresh the graph or record again")
    if report.get("scope") != "current_thread_python_call_events":
        raise ValueError("Unsupported observation scope")
    edges = report.get("edges")
    if not isinstance(edges, list) or len(edges) > 100000:
        raise ValueError("Invalid runtime edge list")
    observed_nodes = report.get("observed_nodes")
    if not isinstance(observed_nodes, list) or len(observed_nodes) > len(graph.nodes):
        raise ValueError("Invalid observed node list")
    if any(not isinstance(n, str) or n not in graph.nodes for n in observed_nodes):
        raise ValueError("Unknown observed node")
    # Validate the entire report before mutating the graph.
    for edge in edges:
        if not isinstance(edge, dict) or any(not isinstance(edge.get(k), str) or edge[k] not in graph.nodes
                                            for k in ("source_id", "target_id")):
            raise ValueError("Runtime edge references an unknown indexed node")
        source = graph.nodes[edge["source_id"]]
        line, count = edge.get("line"), edge.get("call_events")
        if type(line) is not int or not source.start_line <= line <= source.end_line:
            raise ValueError("Runtime caller line is outside its indexed definition")
        if type(count) is not int or not 1 <= count <= 100000:
            raise ValueError("Invalid call event count")
    digest = source_hash(json.dumps(report, sort_keys=True, separators=(",", ":")))
    previous = next((run for run in graph.runtime_runs if run["run_id"] == report["run_id"]), None)
    if previous:
        if previous["digest"] != digest:
            raise ValueError("A different report already uses this run_id")
        return {"imported": False, "reason": "already_imported", "run_id": report["run_id"]}
    if len(graph.runtime_runs) >= 100:
        raise ValueError("Runtime evidence limit reached; refresh the graph before importing more runs")
    for edge in edges:
        graph.add_edge(edge["source_id"], edge["target_id"], "calls", certainty="observed_only",
                       observations=[{"run_id": report["run_id"], "line": edge["line"],
                                      "call_events": edge["call_events"]}])
    graph.runtime_runs.append({"run_id": report["run_id"], "digest": digest,
                               "label": str(report.get("label", ""))[:200],
                               "created_at": str(report.get("created_at", ""))[:100],
                               "scope": report["scope"], "truncated": bool(report.get("truncated")),
                               "exit_status": str(report.get("exit_status", "unknown"))[:30],
                               "observed_nodes": observed_nodes})
    return {"imported": True, "run_id": report["run_id"], "edge_count": len(edges)}
