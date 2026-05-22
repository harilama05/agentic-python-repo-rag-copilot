"""Main codebase agent orchestration.

This module coordinates query planning, retrieval tools, graph analysis, and
optional grounded answer generation while preserving the current response shape.
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from src.agent_core.query_router import LLMQueryRouter, QueryPlan
from src.agent_core.response_models import AgentResponse
from src.agent_core.tools import CodebaseTools
from src.core.constants import (
    QUERY_TYPE_CALLEE,
    QUERY_TYPE_CALLER,
    QUERY_TYPE_DOCUMENTATION,
    QUERY_TYPE_EXPLANATION,
    QUERY_TYPE_IMPACT,
    QUERY_TYPE_LOCATION,
    QUERY_TYPE_MULTI_INTENT,
    QUERY_TYPE_REFERENCE,
    QUERY_TYPE_SEARCH,
)
from src.generation.answer_generator import GroundedAnswerGenerator
from src.generation.llm import GeminiLLM
from src.core.settings import DOCUMENTATION_TOP_K, DEFAULT_TOP_K, FALLBACK_SEARCH_TOP_K


class CodebaseAgent:
    """Repository-scoped agent that answers codebase questions."""

    def __init__(
        self,
        tools: CodebaseTools,
        query_router: LLMQueryRouter,
        llm: Optional[GeminiLLM] = None,
        use_llm: bool = False,
        answer_generator: GroundedAnswerGenerator | None = None,
    ):
        self.tools = tools
        self.query_router = query_router
        self.llm = llm
        self.use_llm = use_llm
        self.answer_generator = answer_generator or (
            GroundedAnswerGenerator(llm) if llm is not None else None
        )

    def _query_plan_to_dict(self, query_plan: QueryPlan | Dict[str, Any] | None) -> Dict[str, Any]:
        if query_plan is None:
            return {}

        if isinstance(query_plan, dict):
            return dict(query_plan)

        return asdict(query_plan)

    def _attach_plan_metadata(
        self,
        response: AgentResponse,
        query_plan: QueryPlan,
    ) -> AgentResponse:
        plan_dict = self._query_plan_to_dict(query_plan)
        response.raw_results["query_plan"] = plan_dict
        response.raw_results["router"] = plan_dict.get("router")
        response.raw_results["router_error"] = plan_dict.get("router_error")

        if not self.use_llm or self.llm is None:
            response.raw_results.setdefault("llm_enabled", False)
            response.raw_results.setdefault("llm_skipped", True)

        return response

    def _build_ambiguous_graph_response(
        self,
        *,
        question: str,
        query_type: str,
        symbol: str,
        tools_used: List[str],
        graph_result: Dict[str, Any],
    ) -> AgentResponse:
        candidates = graph_result.get("candidates", [])

        lines = [
            f"I found multiple symbols matching `{symbol}`.",
            "Please use a more specific qualified name, such as one of these:",
        ]

        for candidate in candidates:
            candidate_symbol = candidate.get("symbol") or candidate.get("qualified_name")
            relative_path = candidate.get("relative_path")
            line_start = candidate.get("line_start")
            line_end = candidate.get("line_end")

            lines.append(
                f"- `{candidate_symbol}` in `{relative_path}:{line_start}-{line_end}`"
            )

        return AgentResponse(
            question=question,
            query_type=query_type,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=candidates,
            raw_results={
                "graph_result": graph_result,
                "ambiguous": True,
            },
        )

    def answer(self, question: str) -> AgentResponse:
        """Answer one user question using routing, tools, and optional LLM output."""
        query_plans = self.query_router.route_many(question)
        response = self._answer_planned_query(
            question=question,
            query_plans=query_plans,
        )
        return self._maybe_generate_llm_answer(response)

    def _answer_single_plan(
        self,
        question: str,
        query_plan: QueryPlan,
    ) -> AgentResponse:
        query_type = query_plan.query_type
        symbol = query_plan.symbol
        effective_question = query_plan.rewritten_query or question
        symbol_resolution = None

        graph_query_types = {
            QUERY_TYPE_CALLER,
            QUERY_TYPE_CALLEE,
            QUERY_TYPE_IMPACT,
        }

        if query_type in graph_query_types and not symbol:
            symbol, symbol_resolution = self._resolve_symbol_for_graph_query(
                query=effective_question,
                top_k=5,
            )

        if query_type == QUERY_TYPE_CALLER and symbol:
            response = self._answer_caller_query(question, symbol)
        elif query_type == QUERY_TYPE_CALLEE and symbol:
            response = self._answer_callee_query(question, symbol)
        elif query_type == QUERY_TYPE_IMPACT and symbol:
            response = self._answer_impact_query(question, symbol)
        elif query_type in graph_query_types and not symbol:
            response = self._answer_graph_query_without_symbol(
                question=question,
                query_type=query_type,
                rewritten_query=effective_question,
                symbol_resolution=symbol_resolution,
            )
        elif query_type == QUERY_TYPE_REFERENCE and symbol:
            response = self._answer_reference_query(question, symbol)
        elif query_type == QUERY_TYPE_LOCATION and symbol:
            response = self._answer_location_query(question, symbol)
        elif query_type == QUERY_TYPE_EXPLANATION and symbol:
            response = self._answer_explanation_query(question, symbol)
        elif query_type == QUERY_TYPE_DOCUMENTATION:
            response = self._answer_documentation_query(effective_question)
            response.question = question
        elif query_type == "count_query":
            response = self._answer_count_query(question, symbol)
        else:
            response = self._answer_search_query(effective_question)
            response.question = question

        self._attach_plan_metadata(response, query_plan)

        if symbol_resolution is not None:
            response.raw_results["symbol_resolution"] = symbol_resolution

        return response

    def _dedupe_sources(
        self,
        sources: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        deduped = []
        seen = set()

        for source in sources:
            key = (
                source.get("relative_path"),
                source.get("line_start"),
                source.get("line_end"),
                source.get("symbol"),
                source.get("type"),
                source.get("role"),
                source.get("source_role"),
            )

            if key in seen:
                continue

            seen.add(key)
            deduped.append(source)

        return deduped

    def _answer_planned_query(
        self,
        question: str,
        query_plans: List[QueryPlan],
    ) -> AgentResponse:
        if not query_plans:
            response = self._answer_search_query(question)
            response.raw_results["query_plans"] = []
            response.raw_results["plan_count"] = 0
            return response

        sub_responses: List[AgentResponse] = []

        for plan in query_plans:
            sub_response = self._answer_single_plan(
                question=question,
                query_plan=plan,
            )
            sub_responses.append(sub_response)

        tools_used: List[str] = []
        sources: List[Dict[str, Any]] = []
        raw_sub_responses = []

        for index, sub_response in enumerate(sub_responses, start=1):
            plan = query_plans[index - 1]
            tools_used.extend(sub_response.tools_used)
            sources.extend(sub_response.sources)

            raw_sub_responses.append(
                {
                    "query_plan": self._query_plan_to_dict(plan),
                    "query_type": sub_response.query_type,
                    "tools_used": sub_response.tools_used,
                    "sources": sub_response.sources,
                    "raw_results": sub_response.raw_results,
                    "fallback_answer": sub_response.answer,
                }
            )

        deduped_tools = list(dict.fromkeys(tools_used))
        deduped_sources = self._dedupe_sources(sources)
        source_excerpts = self._build_source_excerpts(
            deduped_sources,
            context_lines=1,
        )

        if len(query_plans) == 1:
            fallback_answer = sub_responses[0].answer
            query_type = sub_responses[0].query_type
        else:
            fallback_lines = ["I decomposed your question into multiple codebase tasks:"]

            for index, sub_response in enumerate(sub_responses, start=1):
                plan = query_plans[index - 1]
                fallback_lines.append("")
                fallback_lines.append(f"### Part {index}: `{plan.query_type}`")

                if plan.symbol:
                    fallback_lines.append(f"Symbol: `{plan.symbol}`")

                fallback_lines.append(sub_response.answer)

            fallback_answer = "\n".join(fallback_lines)
            query_type = QUERY_TYPE_MULTI_INTENT

        plan_dicts = [self._query_plan_to_dict(plan) for plan in query_plans]
        raw_results = {
            "query_plans": plan_dicts,
            "plans": plan_dicts,
            "routers": [plan.get("router") for plan in plan_dicts],
            "router_errors": [
                plan.get("router_error")
                for plan in plan_dicts
                if plan.get("router_error")
            ],
            "sub_responses": raw_sub_responses,
            "source_excerpts": source_excerpts,
            "plan_count": len(query_plans),
        }

        if len(query_plans) == 1:
            raw_results["query_plan"] = plan_dicts[0]
            raw_results["router"] = plan_dicts[0].get("router")
            raw_results["router_error"] = plan_dicts[0].get("router_error")

        return AgentResponse(
            question=question,
            query_type=query_type,
            answer=fallback_answer,
            tools_used=deduped_tools,
            sources=deduped_sources,
            raw_results=raw_results,
        )

    def _maybe_generate_llm_answer(self, response: AgentResponse) -> AgentResponse:
        """Replace the fallback answer with a grounded LLM answer when enabled."""
        if not self.use_llm or self.answer_generator is None:
            response.raw_results["llm_enabled"] = False
            response.raw_results["llm_skipped"] = True
            return response

        try:
            llm_answer = self.answer_generator.generate(
                question=response.question,
                query_type=response.query_type,
                tools_used=response.tools_used,
                raw_results=response.raw_results,
            )

            response.answer = llm_answer
            response.raw_results["llm_enabled"] = True
            return response

        except Exception as exc:
            response.raw_results["llm_enabled"] = False
            response.raw_results["llm_error"] = str(exc)
            response.raw_results["llm_warning"] = (
                "LLM answer generation is currently unavailable. "
                "Showing fallback tool-based answer."
            )
            return response

    def _answer_reference_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_references("{symbol}", include_definition=False)']
        references = self.tools.find_references(
            symbol_name=symbol,
            include_definition=False,
        )
        definitions = self.tools.find_definitions(symbol) if hasattr(self.tools, "find_definitions") else []

        if not references:
            answer_lines = [
                f"I could not find any usage/reference of `{symbol}` in the indexed codebase."
            ]

            if definitions:
                answer_lines.append("")
                answer_lines.append("I found its definition, but it is not counted as a usage:")
                for definition in definitions:
                    answer_lines.append(
                        f"- `{definition.get('relative_path')}:{definition.get('line_start')}-{definition.get('line_end')}` "
                        f"- `{definition.get('symbol')}`"
                    )

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_REFERENCE,
                answer="\n".join(answer_lines),
                tools_used=tools_used,
                sources=[],
                raw_results={
                    "references": references,
                    "definitions": definitions,
                },
            )

        lines = [f"I found `{symbol}` used/referenced in these locations:"]
        sources = []

        for ref in references:
            relative_path = ref.get("relative_path", "")
            line_start = ref.get("line_start") or ref.get("line_number")
            line_end = ref.get("line_end") or line_start
            line = str(ref.get("line") or "").strip()
            reference_type = ref.get("reference_type") or ref.get("source_role") or "reference"

            if line:
                lines.append(
                    f"- `{relative_path}:{line_start}` "
                    f"({reference_type}) - `{line}`"
                )
            else:
                lines.append(
                    f"- `{relative_path}:{line_start}` "
                    f"({reference_type})"
                )

            sources.append(
                {
                    "relative_path": relative_path,
                    "line_start": line_start,
                    "line_end": line_end,
                    "symbol": ref.get("symbol") or symbol,
                    "type": reference_type,
                    "source_role": reference_type,
                }
            )

        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_REFERENCE,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "references": references,
                "definitions": definitions,
                "source_excerpts": source_excerpts,
            },
        )

    def _answer_location_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_symbol("{symbol}")']
        symbol_results = self.tools.find_symbol(symbol)

        if not symbol_results:
            tools_used.append(f'search_code("{question}")')
            search_results = self.tools.search_code(question, top_k=FALLBACK_SEARCH_TOP_K)

            if not search_results:
                answer = f"I could not find `{symbol}` in the indexed codebase."
                return AgentResponse(
                    question=question,
                    query_type=QUERY_TYPE_LOCATION,
                    answer=answer,
                    tools_used=tools_used,
                    sources=[],
                    raw_results={"symbol_results": [], "search_results": []},
                )

            lines = [f"I could not find an exact symbol match for `{symbol}`, but found related code:"]
            sources = []

            for result in search_results:
                lines.append(
                    f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                    f"- `{result['qualified_name']}` ({result['symbol_type']})"
                )

                sources.append(
                    {
                        "relative_path": result["relative_path"],
                        "line_start": result["start_line"],
                        "line_end": result["end_line"],
                        "symbol": result["qualified_name"],
                        "type": result.get("symbol_type") or result.get("source_type"),
                        "source_role": "definition",
                    }
                )

            source_excerpts = self._build_source_excerpts(sources)

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_LOCATION,
                answer="\n".join(lines),
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "symbol_results": symbol_results,
                    "search_results": search_results,
                    "source_excerpts": source_excerpts,
                },
            )

        lines = [f"`{symbol}` is defined in:"]
        sources = []

        for result in symbol_results:
            lines.append(
                f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                f"- `{result['qualified_name']}` ({result['symbol_type']})"
            )

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": result["qualified_name"],
                    "type": result.get("symbol_type") or result.get("source_type"),
                    "source_role": "definition",
                }
            )

        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_LOCATION,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "symbol_results": symbol_results,
                "source_excerpts": source_excerpts,
            },
        )

    def _answer_explanation_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_symbol("{symbol}")']
        symbol_results = self.tools.find_symbol(symbol)

        if not symbol_results:
            return self._answer_search_query(question)

        first = symbol_results[0]
        tools_used.append(
            f"read_file({first['relative_path']}, "
            f"{first['start_line']}, {first['end_line']})"
        )

        file_content = self.tools.read_file(
            file_path=first["relative_path"],
            start_line=first["start_line"],
            end_line=first["end_line"],
            context_lines=0,
        )

        answer = (
            f"`{first['qualified_name']}` is a `{first['symbol_type']}` defined in "
            f"`{first['relative_path']}:{first['start_line']}-{first['end_line']}`.\n\n"
            f"Code excerpt:\n"
            f"```python\n{file_content['content']}\n```"
        )

        sources = [
            {
                "relative_path": first["relative_path"],
                "line_start": first["start_line"],
                "line_end": first["end_line"],
                "symbol": first["qualified_name"],
                "type": first.get("symbol_type") or first.get("source_type"),
                "source_role": "definition",
            }
        ]

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_EXPLANATION,
            answer=answer,
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "symbol_results": symbol_results,
                "file_content": file_content,
            },
        )

    def _answer_search_query(self, question: str) -> AgentResponse:
        tools_used = [f'search_code("{question}")']
        search_results = self.tools.search_code(question, top_k=DEFAULT_TOP_K)

        if not search_results:
            answer = "I could not find relevant code in the indexed codebase."
            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_SEARCH,
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"search_results": []},
            )

        lines = ["I found these relevant code locations:"]
        sources = []

        for result in search_results:
            relative_path = result.get("relative_path") or result.get("file_path") or ""
            start_line = result.get("start_line") or result.get("line_start")
            end_line = result.get("end_line") or result.get("line_end")
            symbol = (
                result.get("qualified_name")
                or result.get("symbol")
                or result.get("heading")
                or relative_path
            )
            source_type = (
                result.get("symbol_type")
                or result.get("source_type")
                or result.get("type")
                or "unknown"
            )

            lines.append(
                f"- `{relative_path}:{start_line}-{end_line}` "
                f"- `{symbol}` ({source_type})"
            )

            sources.append(
                {
                    "relative_path": relative_path,
                    "line_start": start_line,
                    "line_end": end_line,
                    "symbol": symbol,
                    "type": source_type,
                }
            )

        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_SEARCH,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "search_results": search_results,
                "source_excerpts": source_excerpts,
            },
        )

    def _answer_documentation_query(self, question: str) -> AgentResponse:
        tools_used = [
            f'search_code("{question}", top_k={DOCUMENTATION_TOP_K}, query_type="{QUERY_TYPE_DOCUMENTATION}")'
        ]

        search_results = self.tools.search_code(
            query=question,
            top_k=DOCUMENTATION_TOP_K,
            query_type=QUERY_TYPE_DOCUMENTATION,
        )

        if not search_results:
            answer = (
                "I could not find README or documentation context for this repository. "
                "You can still ask code-level questions about functions, classes, and references."
            )

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_DOCUMENTATION,
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"search_results": []},
            )

        lines = ["I found these relevant documentation/code locations:"]
        sources = []

        for result in search_results:
            source_type = result.get("source_type") or result.get("type") or "unknown"
            symbol = (
                result.get("qualified_name")
                or result.get("symbol")
                or result.get("heading")
                or result.get("relative_path")
            )

            relative_path = result.get("relative_path") or result.get("file_path") or ""
            start_line = result.get("start_line") or result.get("line_start")
            end_line = result.get("end_line") or result.get("line_end")

            lines.append(
                f"- `{relative_path}:{start_line}-{end_line}` "
                f"- `{symbol}` ({source_type})"
            )

            sources.append(
                {
                    "relative_path": relative_path,
                    "line_start": start_line,
                    "line_end": end_line,
                    "symbol": symbol,
                    "type": source_type,
                }
            )

        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_DOCUMENTATION,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "search_results": search_results,
                "source_excerpts": source_excerpts,
            },
        )

    def _answer_count_query(self, question: str, symbol: str | None) -> AgentResponse:
        """Answer queries asking to count symbols or files."""

        # ── File counting ──────────────────────────────────────────
        if symbol in ("file", "python_file", "all_files"):
            file_type = "python" if symbol in ("file", "python_file") else "all"
            tools_used = [f'count_files("{file_type}")']
            result = self.tools.count_files(file_type)

            file_list = result.get("files", [])
            count = result.get("count", 0)
            ext_counts = result.get("counts_by_extension", {})

            # Build a detailed fallback answer listing every file
            if file_type == "python":
                answer = f"🔍 Tìm thấy **{count}** file Python trong codebase:\n"
            else:
                answer = f"🔍 Tìm thấy **{count}** file trong codebase:\n"
                if ext_counts:
                    for ext, ext_count in ext_counts.items():
                        answer += f"\n- {ext_count} file `{ext}`"
                    answer += "\n"

            answer += "\n"
            for f in file_list:
                answer += f"- `{f['relative_path']}` ({f['line_count']} dòng)\n"

            # Sources: one entry per file, pointing to the whole file
            sources = [
                {
                    "relative_path": f["relative_path"],
                    "line_start": 1,
                    "line_end": f["line_count"],
                    "symbol": f["relative_path"].split("/")[-1],
                    "type": f["extension"],
                }
                for f in file_list
            ]

            return AgentResponse(
                question=question,
                query_type="count_query",
                answer=answer,
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "count_result": result,
                },
            )

        # ── Symbol counting (original behavior) ───────────────────
        symbol_type = symbol if symbol in ("function", "class", "method") else "all"
        tools_used = [f'count_symbols("{symbol_type}")']

        result = self.tools.count_symbols(symbol_type)

        if symbol_type == "all":
            answer = f"🔍 Đã tìm thấy tổng cộng **{result['count']}** symbols trong codebase:\n"
            for stype, count in result.get("counts_by_type", {}).items():
                answer += f"\n- {count} {stype}s"
        else:
            answer = f"🔍 Đã tìm thấy tổng cộng **{result['count']}** {symbol_type}s trong codebase."

        sources = result.get("items", [])

        return AgentResponse(
            question=question,
            query_type="count_query",
            answer=answer,
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "count_result": result,
            },
        )

    def _resolve_symbol_for_graph_query(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[str | None, Dict[str, Any]]:
        """Resolve a natural-language graph query into a concrete code symbol."""
        search_results = self.tools.search_code(query, top_k=top_k)
        candidates = []

        for rank, result in enumerate(search_results):
            if result.get("source_type") != "code":
                continue

            symbol = result.get("qualified_name") or result.get("symbol_name")
            symbol_type = result.get("symbol_type")

            if not symbol:
                continue

            if symbol_type not in {"function", "method", "class"}:
                continue

            score = 100 - rank

            if "." in symbol:
                score += 10

            if symbol_type == "method":
                score += 8

            if symbol_type == "function":
                score += 5

            candidates.append(
                {
                    "symbol": symbol,
                    "symbol_type": symbol_type,
                    "relative_path": result.get("relative_path"),
                    "line_start": result.get("start_line"),
                    "line_end": result.get("end_line"),
                    "score": score,
                    "final_score": result.get("final_score"),
                    "cross_encoder_score": result.get("cross_encoder_score"),
                    "source_type": result.get("source_type"),
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        resolved_symbol = candidates[0]["symbol"] if candidates else None

        return resolved_symbol, {
            "query": query,
            "resolved_symbol": resolved_symbol,
            "candidates": candidates,
            "raw_search_results": search_results,
        }

    def _answer_caller_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_callers("{symbol}")']
        graph_result = self.tools.find_callers(symbol)

        if graph_result.get("ambiguous"):
            return self._build_ambiguous_graph_response(
                question=question,
                query_type=QUERY_TYPE_CALLER,
                symbol=symbol,
                tools_used=tools_used,
                graph_result=graph_result,
            )

        resolved_symbol = graph_result.get("resolved_symbol") or symbol
        targets = graph_result.get("targets", [])
        callers = graph_result.get("callers", [])

        if not targets:
            answer = f"I could not find `{symbol}` in the code graph."
            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_CALLER,
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"graph_result": graph_result},
            )

        if not callers:
            answer = f"I found `{resolved_symbol}`, but could not find any callers in the code graph."
            sources = targets
            source_excerpts = self._build_source_excerpts(sources)

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_CALLER,
                answer=answer,
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "graph_result": graph_result,
                    "source_excerpts": source_excerpts,
                },
            )

        lines = [f"`{resolved_symbol}` is called by:"]

        for caller in callers:
            lines.append(
                f"- `{caller['symbol']}` in "
                f"`{caller['relative_path']}:{caller['line_start']}-{caller['line_end']}`"
            )

        sources = targets + callers
        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_CALLER,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "graph_result": graph_result,
                "source_excerpts": source_excerpts,
            },
        )

    def _answer_callee_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_callees("{symbol}")']
        graph_result = self.tools.find_callees(symbol)

        if graph_result.get("ambiguous"):
            return self._build_ambiguous_graph_response(
                question=question,
                query_type=QUERY_TYPE_CALLEE,
                symbol=symbol,
                tools_used=tools_used,
                graph_result=graph_result,
            )

        resolved_symbol = graph_result.get("resolved_symbol") or symbol
        sources_nodes = graph_result.get("sources", [])
        callees = graph_result.get("callees", [])

        if not sources_nodes:
            answer = f"I could not find `{symbol}` in the code graph."
            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_CALLEE,
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"graph_result": graph_result},
            )

        if not callees:
            answer = f"I found `{resolved_symbol}`, but it does not call any indexed functions or methods."
            sources = sources_nodes

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_CALLEE,
                answer=answer,
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "graph_result": graph_result,
                },
            )

        lines = [f"`{resolved_symbol}` calls:"]

        for callee in callees:
            lines.append(
                f"- `{callee['symbol']}` in "
                f"`{callee['relative_path']}:{callee['line_start']}-{callee['line_end']}`"
            )

        sources = sources_nodes + callees
        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_CALLEE,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "graph_result": graph_result,
                "source_excerpts": source_excerpts,
            },
        )

    def _answer_impact_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'impact_analysis("{symbol}")']
        graph_result = self.tools.impact_analysis(symbol)

        if graph_result.get("ambiguous"):
            return self._build_ambiguous_graph_response(
                question=question,
                query_type=QUERY_TYPE_IMPACT,
                symbol=symbol,
                tools_used=tools_used,
                graph_result=graph_result,
            )

        resolved_symbol = graph_result.get("resolved_symbol") or symbol
        targets = graph_result.get("targets", [])
        affected = graph_result.get("affected", [])

        if not targets:
            answer = f"I could not find `{symbol}` in the code graph."
            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_IMPACT,
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"graph_result": graph_result},
            )

        if not affected:
            answer = (
                f"I found `{resolved_symbol}`, but the code graph did not find any callers "
                "that would be directly affected."
            )
            sources = targets
            source_excerpts = self._build_source_excerpts(sources)

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_IMPACT,
                answer=answer,
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "graph_result": graph_result,
                    "source_excerpts": source_excerpts,
                },
            )

        lines = [
            f"If `{resolved_symbol}` is changed or removed, these code locations may be affected:"
        ]

        for node in affected:
            lines.append(
                f"- `{node['symbol']}` in "
                f"`{node['relative_path']}:{node['line_start']}-{node['line_end']}`"
            )

        sources = targets + affected
        source_excerpts = self._build_source_excerpts(sources)

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_IMPACT,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "graph_result": graph_result,
                "source_excerpts": source_excerpts,
            },
        )

    def _build_source_excerpts(
        self,
        sources: List[Dict[str, Any]],
        context_lines: int = 1,
    ) -> List[Dict[str, Any]]:
        """Read source excerpts so grounded answers can explain concrete code."""
        excerpts: List[Dict[str, Any]] = []
        seen = set()

        for source in sources:
            relative_path = source.get("relative_path")
            line_start = source.get("line_start")
            line_end = source.get("line_end")

            if not relative_path or line_start is None or line_end is None:
                continue

            key = (relative_path, line_start, line_end)

            if key in seen:
                continue

            seen.add(key)

            try:
                file_content = self.tools.read_file(
                    file_path=relative_path,
                    start_line=line_start,
                    end_line=line_end,
                    context_lines=context_lines,
                )

                excerpts.append(
                    {
                        "relative_path": relative_path,
                        "line_start": file_content["start_line"],
                        "line_end": file_content["end_line"],
                        "symbol": source.get("symbol"),
                        "role": source.get("source_role") or source.get("role") or source.get("type"),
                        "content": file_content["content"],
                    }
                )

            except Exception as exc:
                excerpts.append(
                    {
                        "relative_path": relative_path,
                        "line_start": line_start,
                        "line_end": line_end,
                        "symbol": source.get("symbol"),
                        "role": source.get("source_role") or source.get("role") or source.get("type"),
                        "error": str(exc),
                    }
                )

        return excerpts

    def _answer_graph_query_without_symbol(
        self,
        question: str,
        query_type: str,
        rewritten_query: str,
        symbol_resolution: Dict[str, Any] | None,
    ) -> AgentResponse:
        tools_used = [f'search_code("{rewritten_query}")']
        raw_search_results = []

        if symbol_resolution:
            raw_search_results = symbol_resolution.get("raw_search_results", [])

        sources = []

        for result in raw_search_results:
            if result.get("source_type") != "code":
                continue

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": result.get("qualified_name") or result.get("symbol_name"),
                    "type": result.get("symbol_type"),
                }
            )

        answer = (
            "I understand this is a graph or impact question, "
            "but I could not resolve a specific function, class, or method to run graph analysis on. "
            "Please ask with a concrete symbol, for example `TaskService.create_task`."
        )

        if sources:
            answer += (
                "\n\nI found a few code locations that may be related, "
                "but not enough to make a precise caller/callee/impact conclusion."
            )

        return AgentResponse(
            question=question,
            query_type=query_type,
            answer=answer,
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "symbol_resolution": symbol_resolution,
                "search_results": raw_search_results,
            },
        )
