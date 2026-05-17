from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from src.llm import GeminiLLM
from src.prompts import SYSTEM_PROMPT, build_grounded_user_prompt
from src.tools import CodebaseTools
from src.constants import (
    QUERY_TYPE_CALLEE,
    QUERY_TYPE_CALLER,
    QUERY_TYPE_DOCUMENTATION,
    QUERY_TYPE_EXPLANATION,
    QUERY_TYPE_IMPACT,
    QUERY_TYPE_LOCATION,
    QUERY_TYPE_REFERENCE,
    QUERY_TYPE_SEARCH,
)
from src.settings import DOCUMENTATION_TOP_K, DEFAULT_TOP_K, FALLBACK_SEARCH_TOP_K
from src.query_router import LLMQueryRouter, QueryPlan

@dataclass
class AgentResponse:
    question: str
    query_type: str
    answer: str
    tools_used: List[str]
    sources: List[Dict[str, Any]]
    raw_results: Dict[str, Any]


class CodebaseAgent:
    def __init__(
        self,
        tools: CodebaseTools,
        query_router: LLMQueryRouter,
        llm: Optional[GeminiLLM] = None,
        use_llm: bool = False,
    ):
        self.tools = tools
        self.query_router = query_router
        self.llm = llm
        self.use_llm = use_llm

    def answer(self, question: str) -> AgentResponse:
        query_plan = self.query_router.route(question)

        query_type = query_plan.query_type
        symbol = query_plan.symbol
        effective_question = query_plan.rewritten_query or question

        symbol_resolution = None

        graph_query_types = {
            QUERY_TYPE_CALLER,
            QUERY_TYPE_CALLEE,
            QUERY_TYPE_IMPACT,
        }

        # If this is a graph query but the router could not extract a concrete
        # symbol, resolve the symbol through repository search first.
        #
        # This automatically uses Fast or Accurate mode because search_code()
        # lives inside CodebaseTools.
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

        else:
            response = self._answer_search_query(effective_question)
            response.question = question

        response.raw_results["query_plan"] = asdict(query_plan)

        if symbol_resolution is not None:
            response.raw_results["symbol_resolution"] = symbol_resolution

        return self._maybe_generate_llm_answer(response)

    def _maybe_generate_llm_answer(self, response: AgentResponse) -> AgentResponse:
        """
        Replace the rule-based answer with an LLM-generated grounded answer
        when LLM generation is enabled.
        """
        if not self.use_llm or self.llm is None:
            return response

        try:
            user_prompt = build_grounded_user_prompt(
                question=response.question,
                query_type=response.query_type,
                tools_used=response.tools_used,
                raw_results=response.raw_results,
            )

            llm_answer = self.llm.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
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
        tools_used = [f'find_references("{symbol}")']
        references = self.tools.find_references(symbol)

        if not references:
            answer = f"I could not find any references to `{symbol}` in the indexed codebase."
            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_REFERENCE,
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"references": references},
            )

        lines = [f"I found `{symbol}` in these locations:"]

        sources = []

        for ref in references:
            line_type = "definition" if ref["is_definition"] else "reference"
            lines.append(
                f"- `{ref['relative_path']}:{ref['line_number']}` "
                f"({line_type}) — `{ref['line'].strip()}`"
            )

            sources.append(
                {
                    "relative_path": ref["relative_path"],
                    "line_start": ref["line_number"],
                    "line_end": ref["line_number"],
                    "type": line_type,
                }
            )

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_REFERENCE,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"references": references},
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
                    f"— `{result['qualified_name']}` ({result['symbol_type']})"
                )

                sources.append(
                    {
                        "relative_path": result["relative_path"],
                        "line_start": result["start_line"],
                        "line_end": result["end_line"],
                        "symbol": result["qualified_name"],
                    }
                )

            return AgentResponse(
                question=question,
                query_type=QUERY_TYPE_LOCATION,
                answer="\n".join(lines),
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "symbol_results": symbol_results,
                    "search_results": search_results,
                },
            )

        lines = [f"`{symbol}` is defined in:"]
        sources = []

        for result in symbol_results:
            lines.append(
                f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                f"— `{result['qualified_name']}` ({result['symbol_type']})"
            )

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": result["qualified_name"],
                }
            )

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_LOCATION,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"symbol_results": symbol_results},
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
            lines.append(
                f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                f"— `{result['qualified_name']}` ({result['symbol_type']})"
            )

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": result["qualified_name"],
                }
            )

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_SEARCH,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"search_results": search_results},
        )
    
    def _answer_documentation_query(self, question: str) -> AgentResponse:
        tools_used = [f'search_code("{question}")']
        search_results = self.tools.search_code(question, top_k=DOCUMENTATION_TOP_K)

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
            source_type = result.get("source_type") or "unknown"
            symbol = result.get("qualified_name") or result.get("heading")

            lines.append(
                f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                f"— `{symbol}` ({source_type})"
            )

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": symbol,
                    "type": source_type,
                }
            )

        return AgentResponse(
            question=question,
            query_type=QUERY_TYPE_DOCUMENTATION,
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"search_results": search_results},
        )
    
    def _resolve_symbol_for_graph_query(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[str | None, Dict[str, Any]]:
        """
        Resolve a natural-language graph query into a concrete code symbol.

        This uses self.tools.search_code(), so:
        - Fast mode uses hybrid retrieval.
        - Accurate mode uses hybrid retrieval + Cross-Encoder reranking.
        """
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

            # Prefer qualified methods/classes for graph analysis.
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

        targets = graph_result["targets"]
        callers = graph_result["callers"]

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
            answer = f"I found `{symbol}`, but could not find any callers in the code graph."
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

        lines = [f"`{symbol}` is called by:"]

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

        sources_nodes = graph_result["sources"]
        callees = graph_result["callees"]

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
            answer = f"I found `{symbol}`, but it does not call any indexed functions or methods."
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

        lines = [f"`{symbol}` calls:"]

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

        targets = graph_result["targets"]
        affected = graph_result["affected"]

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
                f"I found `{symbol}`, but the code graph did not find any callers "
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
            f"If `{symbol}` is changed or removed, these code locations may be affected:"
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
        """
        Read source excerpts for graph/search sources so the LLM can explain
        relationships with concrete code context.
        """
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
                        "role": source.get("role") or source.get("type"),
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
                        "role": source.get("role") or source.get("type"),
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
            "Tôi hiểu đây là câu hỏi về quan hệ hoặc ảnh hưởng trong code, "
            "nhưng chưa xác định được function/class/method cụ thể để chạy phân tích graph. "
            "Bạn có thể hỏi kèm tên symbol cụ thể, ví dụ `TaskService.create_task`."
        )

        if sources:
            answer += (
                "\n\nTôi tìm thấy một vài đoạn code có thể liên quan, "
                "nhưng chưa đủ chắc chắn để kết luận graph impact/caller/callee."
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