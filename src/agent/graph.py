"""
Agent graph - defines the state-machine pipeline for the agentic RAG flow.
"""

from typing import Optional

from src.agent.query_router import LLMQueryRouter
from src.agent.router import route_query, should_use_symbol_search
from src.agent.state import AgentState
from src.agent.tools import AgentTools
from src.generation.answer_generator import AnswerGenerator
from src.generation.citation_builder import (
    build_citations,
    build_citations_from_sources,
    build_source_dicts,
)
from src.generation.context_builder import build_context
from src.reranking.reranker import Reranker
from src.retrieval.retriever import Retriever
from src.schemas import AgentResponse, SearchResult


class AgentGraph:
    """
    State-machine agent implementing route -> retrieve -> rerank -> generate.
    """

    def __init__(
        self,
        tools: AgentTools,
        retriever: Retriever,
        reranker: Optional[Reranker] = None,
        generator: Optional[AnswerGenerator] = None,
        query_router: Optional[LLMQueryRouter] = None,
    ):
        self.tools = tools
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator
        self.query_router = query_router

    def _node_route(self, state: AgentState) -> AgentState:
        return route_query(state, query_router=self.query_router)

    def _relationship_results_to_search_results(
        self,
        *,
        query_type: str,
        symbol: str,
        items: list[dict],
        no_results_text: str | None = None,
    ) -> list[SearchResult]:
        label_by_query_type = {
            "reference_query": "references",
            "caller_query": "callers",
            "callee_query": "callees",
            "impact_query": "affected callers",
        }
        label = label_by_query_type.get(query_type, "relationships")

        if not items:
            return [
                SearchResult(
                    chunk_id=f"code-graph:{query_type}:{symbol}:empty",
                    text=no_results_text
                    or f"Code graph found no {label} for `{symbol}`.",
                    metadata={
                        "relative_path": "code_graph",
                        "start_line": 0,
                        "end_line": 0,
                        "symbol_name": symbol,
                        "qualified_name": symbol,
                        "symbol_type": "code_graph",
                        "source": "graph",
                        "query_type": query_type,
                    },
                    score=1.0,
                )
            ]

        results: list[SearchResult] = []
        for index, item in enumerate(items, start=1):
            relative_path = item.get("relative_path", "unknown")
            start_line = item.get("start_line") or item.get("line_number") or 0
            end_line = item.get("end_line") or start_line
            qualified_name = item.get("qualified_name") or item.get("symbol_name", "")
            symbol_type = item.get("symbol_type", "")

            text = (
                f"Code graph result for `{symbol}` ({label}): "
                f"`{qualified_name}` ({symbol_type}) at "
                f"{relative_path}:{start_line}-{end_line}."
            )

            results.append(
                SearchResult(
                    chunk_id=item.get(
                        "chunk_id",
                        f"code-graph:{query_type}:{symbol}:{index}",
                    ),
                    text=text,
                    metadata={
                        "relative_path": relative_path,
                        "start_line": start_line,
                        "end_line": end_line,
                        "symbol_name": item.get("symbol_name", ""),
                        "qualified_name": qualified_name,
                        "symbol_type": symbol_type,
                        "source": item.get("source", "graph"),
                        "query_type": query_type,
                    },
                    score=1.0,
                )
            )

        return results

    def _node_symbol_retrieve(self, state: AgentState) -> AgentState:
        symbol = state.get("symbol_candidate", "")
        query_type = state.get("query_type", "")

        if query_type in ("reference_query", "caller_query") and symbol:
            refs = self.tools.find_references(symbol)
            state["tools_used"] = state.get("tools_used", []) + [
                f'find_references("{symbol}")'
            ]

            state["search_results"] = self.tools.search_code(symbol, top_k=3)
            state["sources"] = refs

            references = [ref for ref in refs if not ref.get("is_definition", False)]
            definitions = [ref for ref in refs if ref.get("is_definition", False)]
            no_results_text = (
                f"`{symbol}` is defined, but no callers/references were found."
                if definitions
                else f"No references found for `{symbol}`."
            )
            graph_results = self._relationship_results_to_search_results(
                query_type=query_type,
                symbol=symbol,
                items=references,
                no_results_text=no_results_text,
            )
            state["search_results"] = graph_results + state["search_results"]

            return state

        if query_type == "callee_query" and symbol:
            graph_result = self.tools.find_callees(symbol)
            state["tools_used"] = state.get("tools_used", []) + [
                f'find_callees("{symbol}")'
            ]

            callees = graph_result.get("callees", [])
            state["sources"] = callees
            state["search_results"] = self.tools.search_code(symbol, top_k=3)
            graph_results = self._relationship_results_to_search_results(
                query_type=query_type,
                symbol=symbol,
                items=callees,
            )
            state["search_results"] = graph_results + state["search_results"]

            return state

        if query_type == "impact_query" and symbol:
            graph_result = self.tools.impact_analysis(symbol)
            state["tools_used"] = state.get("tools_used", []) + [
                f'impact_analysis("{symbol}")'
            ]

            affected = graph_result.get("affected", [])
            state["sources"] = affected
            state["search_results"] = self.tools.search_code(symbol, top_k=3)
            graph_results = self._relationship_results_to_search_results(
                query_type=query_type,
                symbol=symbol,
                items=affected,
            )
            state["search_results"] = graph_results + state["search_results"]

            return state

        results = self.tools.find_symbol(symbol)
        state["tools_used"] = state.get("tools_used", []) + [
            f'find_symbol("{symbol}")'
        ]

        if not results:
            query = state.get("rewritten_query") or state["question"]
            results = self.tools.search_code(query, top_k=5)
            state["tools_used"] = state.get("tools_used", []) + [
                f'search_code("{query}")'
            ]

        state["search_results"] = results
        return state

    def _node_hybrid_retrieve(self, state: AgentState) -> AgentState:
        question = state["question"]
        query = state.get("rewritten_query") or question
        results = self.tools.search_code(query, top_k=10)
        state["tools_used"] = state.get("tools_used", []) + [
            f'search_code("{query}")'
        ]
        state["search_results"] = results
        return state

    def _node_rerank(self, state: AgentState) -> AgentState:
        results = state.get("search_results", [])

        if self.reranker and results:
            state["tools_used"] = state.get("tools_used", []) + ["rerank"]
            state["reranked_results"] = self.reranker.rerank(
                query=state["question"],
                results=results,
                top_k=5,
            )
        else:
            state["reranked_results"] = results[:5]

        return state

    def _node_generate(self, state: AgentState) -> AgentState:
        if state.get("answer"):
            results = state.get("reranked_results") or state.get("search_results", [])
            sources = state.get("sources") or build_source_dicts(results)
            state["sources"] = sources
            state["citations"] = (
                build_citations_from_sources(sources)
                if sources
                else build_citations(results)
            )
            return state

        results = state.get("reranked_results") or state.get("search_results", [])

        if self.generator:
            gen_result = self.generator.generate(
                question=state["question"],
                results=results,
            )
            state["answer"] = gen_result["answer"]
            state["token_usage"] = gen_result.get("token_usage", {})
        else:
            context = build_context(results)
            state["answer"] = (
                "*(LLM not configured - showing retrieved context)*\n\n" + context
            )

        sources = state.get("sources") or build_source_dicts(results)
        state["sources"] = sources
        state["citations"] = (
            build_citations_from_sources(sources)
            if sources
            else build_citations(results)
        )
        return state

    def invoke(self, question: str) -> AgentResponse:
        state: AgentState = {"question": question}

        state = self._node_route(state)

        next_node = should_use_symbol_search(state)
        if next_node == "symbol_retrieve":
            state = self._node_symbol_retrieve(state)
        else:
            state = self._node_hybrid_retrieve(state)

        state = self._node_rerank(state)
        state = self._node_generate(state)

        return AgentResponse(
            question=state.get("question", question),
            answer=state.get("answer", "No answer generated."),
            sources=state.get("sources", []),
            citations=state.get("citations", []),
            tools_used=state.get("tools_used", []),
            query_type=state.get("query_type", ""),
            raw_results={
                "router": state.get("router", ""),
                "router_confidence": state.get("router_confidence", 0.0),
                "router_reason": state.get("router_reason", ""),
                "rewritten_query": state.get("rewritten_query", ""),
                "symbol_candidate": state.get("symbol_candidate", ""),
            },
            token_usage=state.get("token_usage", {}),
        )


def create_agent_graph(
    tools: AgentTools,
    retriever: Retriever,
    reranker: Optional[Reranker] = None,
    generator: Optional[AnswerGenerator] = None,
    query_router: Optional[LLMQueryRouter] = None,
) -> AgentGraph:
    return AgentGraph(
        tools=tools,
        retriever=retriever,
        reranker=reranker,
        generator=generator,
        query_router=query_router,
    )
