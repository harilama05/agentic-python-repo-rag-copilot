"""Validated repository tools and evidence IDs exposed to the agent."""

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agent_core.tools import CodebaseTools
from src.core.settings import AGENT_TOOL_RESULT_CHARS


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchArgs(Arguments):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    query_type: Literal["search_query", "documentation_query"] = "search_query"


class SymbolArgs(Arguments):
    symbol_name: str = Field(min_length=1, max_length=1000)


class ReadArgs(Arguments):
    file_path: str = Field(min_length=1, max_length=1000)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class GraphArgs(SymbolArgs):
    max_depth: int = Field(default=3, ge=1, le=5)


class ReferenceArgs(SymbolArgs):
    include_definition: bool = False
    max_results: int = Field(default=20, ge=1, le=30)


class CountSymbolsArgs(Arguments):
    symbol_type: Literal["all", "function", "class", "method"] = "all"


class CountFilesArgs(Arguments):
    file_type: Literal["python", "all"] = "all"


QUERY_TYPES = Literal[
    "documentation_query", "location_query", "reference_query", "explanation_query",
    "search_query", "caller_query", "callee_query", "impact_query", "flow_query",
    "count_query", "multi_intent_query",
]


class FinishArgs(Arguments):
    answer: str = Field(min_length=1, max_length=16000)
    source_ids: list[str] = Field(max_length=30)
    query_type: QUERY_TYPES
    status: Literal["completed", "insufficient_evidence"] = "completed"


@dataclass
class ToolSpec:
    arguments: type[Arguments]
    description: str


SPECS = {
    "search_code": ToolSpec(SearchArgs, "Search indexed code or documentation. Rewrite search terms when results are irrelevant."),
    "find_definitions": ToolSpec(SymbolArgs, "Find definitions of an explicit function/class/method name."),
    "read_file": ToolSpec(ReadArgs, "Read original indexed file lines from the database, up to 80 lines per call. Never reads the local filesystem."),
    "find_references": ToolSpec(ReferenceArgs, "Find lexical usages of a symbol in indexed Python source."),
    "find_callers": ToolSpec(SymbolArgs, "Find direct callers in the static code graph. Disambiguate with node_id or path::qualified_name."),
    "find_callees": ToolSpec(SymbolArgs, "Find direct callees in the static code graph. Results are approximate."),
    "impact_analysis": ToolSpec(GraphArgs, "Find transitive callers potentially affected by a change, to a bounded depth."),
    "trace_flow": ToolSpec(GraphArgs, "Explore bounded static call relationships starting at a symbol. This does not prove runtime order."),
    "count_symbols": ToolSpec(CountSymbolsArgs, "Count indexed graph functions/classes/methods exactly."),
    "count_files": ToolSpec(CountFilesArgs, "List and count indexed files. Counts cover supported indexed formats only."),
    "finish_answer": ToolSpec(FinishArgs, "Finish in the user's language. Select only evidence IDs returned by tools. Use insufficient_evidence when unable to verify the answer."),
}


def _inline_schema(schema: dict) -> dict:
    """Flatten Pydantic refs into a portable tool declaration schema."""
    definitions = schema.get("$defs", {})

    def visit(value):
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return visit(definitions[value["$ref"].split("/")[-1]])
        return {key: visit(item) for key, item in value.items()
                if key not in {"$defs", "title", "additionalProperties"}}

    return visit(schema)


class ToolRegistry:
    """One instance per question: evidence cannot leak across sessions/runs."""

    def __init__(self, tools: CodebaseTools):
        self.tools = tools
        self.evidence: dict[str, dict] = {}
        self._evidence_keys: dict[tuple, str] = {}
        self.has_count_evidence = False

    def declarations(self) -> list[dict]:
        return [{"name": name, "description": spec.description,
                 "parameters": _inline_schema(spec.arguments.model_json_schema())}
                for name, spec in SPECS.items()]

    def _collect_sources(self, value: Any) -> list[dict]:
        candidates = []
        if isinstance(value, list):
            for item in value:
                candidates.extend(self._collect_sources(item))
        elif isinstance(value, dict):
            path = value.get("relative_path")
            start = value.get("line_start", value.get("start_line"))
            end = value.get("line_end", value.get("end_line"))
            if path and isinstance(start, int) and isinstance(end, int) and 1 <= start <= end:
                try:
                    lines = self.tools._read_file_from_db(path)
                    if end <= len(lines):
                        candidates.append({"relative_path": path, "line_start": start,
                                           "line_end": end, "symbol": value.get("symbol") or value.get("qualified_name"),
                                           "type": value.get("type") or value.get("symbol_type") or "source"})
                except (ValueError, FileNotFoundError):
                    pass
            # Only structured result containers, never strings of source code.
            for key, item in value.items():
                if key not in {"metadata", "text", "content", "code"} and isinstance(item, (list, dict)):
                    candidates.extend(self._collect_sources(item))
        return candidates

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in SPECS or name == "finish_answer":
            raise ValueError(f"Unknown executable tool: {name}")
        args = SPECS[name].arguments.model_validate(arguments).model_dump(exclude_none=True)
        if name == "read_file":
            args["end_line"] = min(args.get("end_line", args["start_line"] + 79), args["start_line"] + 79)
        result = getattr(self.tools, name)(**args)

        def compact(value):
            if isinstance(value, str):
                return value if len(value) <= 3000 else value[:3000] + "\n[truncated; read a smaller line range]"
            if isinstance(value, list):
                items = [compact(item) for item in value[:10]]
                if len(value) > 10:
                    items.append({"truncated_items": len(value) - 10})
                return items
            if isinstance(value, dict):
                return {key: compact(item) for key, item in value.items()}
            return value

        data = compact(result)
        sources = []
        for source in self._collect_sources(data)[:8]:
            key = (source["relative_path"], source["line_start"], source["line_end"])
            evidence_id = self._evidence_keys.get(key)
            if evidence_id is None:
                evidence_id = f"S{len(self.evidence) + 1}"
                excerpt = self.tools.read_file(source["relative_path"], source["line_start"],
                                               min(source["line_end"], source["line_start"] + 39))
                self.evidence[evidence_id] = {**source, "id": evidence_id,
                                              "content": excerpt["content"][:3000]}
                self._evidence_keys[key] = evidence_id
            sources.append({**source, "id": evidence_id})
        if name in {"count_files", "count_symbols"}:
            self.has_count_evidence = True
        payload = {"ok": True, "data": data, "sources": sources}
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        if len(serialized) > AGENT_TOOL_RESULT_CHARS:
            payload["data"] = {"preview": json.dumps(data, ensure_ascii=False, default=str)[:4000],
                               "truncated": True, "hint": "Narrow the query or read a smaller range."}
        return payload

    def finish(self, arguments: dict) -> tuple[FinishArgs, list[dict]]:
        final = FinishArgs.model_validate(arguments)
        unknown = set(final.source_ids) - self.evidence.keys()
        if unknown:
            raise ValueError(f"Unknown evidence IDs: {sorted(unknown)}")
        if final.status == "completed" and not final.source_ids and not (self.has_count_evidence and final.query_type == "count_query"):
            raise ValueError("Retrieve repository evidence before completing the answer.")
        return final, [self.evidence[key] for key in dict.fromkeys(final.source_ids)]
