"""
Agent graph — defines the LangGraph-style state machine for the
agentic RAG pipeline.

Flow:
    route_query → (symbol_retrieve | hybrid_retrieve) → rerank → generate → respond

This is a simplified graph that doesn't require the langgraph package.
It implements the same pattern (nodes + edges + conditional routing)
using plain Python.
"""

from typing import Any, Callable, Dict, List, Optional

from src.agent.state import AgentState
from src.agent.router import route_query, should_use_symbol_search
from src.agent.tools import AgentTools
from src.retrieval.retriever import Retriever
from src.reranking.reranker import Reranker
from src.generation.answer_generator import AnswerGenerator
from src.generation.context_builder import build_context
from src.generation.citation_builder import build_citations, build_source_dicts
from src.schemas import AgentResponse, SearchResult


class AgentGraph:
    """
    State-machine agent implementing a multi-step RAG pipeline.

    Nodes:
    1. ``route`` — classify query, extract symbol
    2. ``retrieve`` — hybrid or symbol search
    3. ``rerank`` — cross-encoder reranking
    4. ``generate`` — LLM answer generation
    """

    def __init__(
        self,
        tools: AgentTools,
        retriever: Retriever,
        reranker: Optional[Reranker] = None,
        generator: Optional[AnswerGenerator] = None,
    ):
        self.tools = tools
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator

    # ── Node: Route ──────────────────────────────────────────────────

    def _node_route(self, state: AgentState) -> AgentState:
        return route_query(state)

    # ── Node: Symbol Retrieve ────────────────────────────────────────

    def _node_symbol_retrieve(self, state: AgentState) -> AgentState:
        symbol = state.get("symbol_candidate", "")
        query_type = state.get("query_type", "")

        if query_type == "reference_query" and symbol:
            refs = self.tools.find_references(symbol)
            state["tools_used"] = state.get("tools_used", []) + [
                f'find_references("{symbol}")'
            ]

            # Also do a hybrid search for additional context
            results = self.tools.search_code(symbol, top_k=3)
            state["search_results"] = results
            state["sources"] = [
                {
                    "relative_path": r.get("relative_path", ""),
                    "line_number": r.get("line_number", 0),
                    "line": r.get("line", ""),
                    "is_definition": r.get("is_definition", False),
                }
                for r in refs
            ]
            # Build answer from references
            if refs:
                lines = [f"Found `{symbol}` in these locations:"]
                for ref in refs:
                    ref_type = "definition" if ref["is_definition"] else "reference"
                    lines.append(
                        f"- `{ref['relative_path']}:{ref['line_number']}` "
                        f"({ref_type}) — `{ref['line'].strip()}`"
                    )
                state["answer"] = "\n".join(lines)
            else:
                state["answer"] = f"No references found for `{symbol}`."

            return state

        # Default: symbol search
        results = self.tools.find_symbol(symbol)
        state["tools_used"] = state.get("tools_used", []) + [
            f'find_symbol("{symbol}")'
        ]

        if not results:
            # Fallback to hybrid search
            results = self.tools.search_code(state["question"], top_k=5)
            state["tools_used"] = state.get("tools_used", []) + [
                f'search_code("{state["question"]}")'
            ]

        state["search_results"] = results
        return state

    # ── Node: Hybrid Retrieve ────────────────────────────────────────

    def _node_hybrid_retrieve(self, state: AgentState) -> AgentState:
        question = state["question"]
        results = self.tools.search_code(question, top_k=10)
        state["tools_used"] = state.get("tools_used", []) + [
            f'search_code("{question}")'
        ]
        state["search_results"] = results
        return state

    # ── Node: Rerank ─────────────────────────────────────────────────

    def _node_rerank(self, state: AgentState) -> AgentState:
        results = state.get("search_results", [])

        if self.reranker and results:
            state["tools_used"] = state.get("tools_used", []) + ["rerank"]
            reranked = self.reranker.rerank(
                query=state["question"],
                results=results,
                top_k=5,
            )
            state["reranked_results"] = reranked
        else:
            state["reranked_results"] = results[:5]

        return state

    # ── Node: Generate ───────────────────────────────────────────────

    def _node_generate(self, state: AgentState) -> AgentState:
        # If answer was already built (e.g. reference_query), skip LLM
        if state.get("answer"):
            results = state.get("reranked_results") or state.get("search_results", [])
            state["citations"] = build_citations(results)
            state["sources"] = state.get("sources") or build_source_dicts(results)
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
            # No LLM configured — return structured context
            context = build_context(results)
            state["answer"] = (
                "*(LLM not configured — showing retrieved context)*\n\n" + context
            )

        state["citations"] = build_citations(results)
        state["sources"] = build_source_dicts(results)
        return state

    # ── Execute the graph ────────────────────────────────────────────

    def invoke(self, question: str) -> AgentResponse:
        """
        Run the full agent pipeline and return an ``AgentResponse``.
        """
        state: AgentState = {"question": question}

        # Step 1: Route
        state = self._node_route(state)

        # Step 2: Retrieve (conditional)
        next_node = should_use_symbol_search(state)
        if next_node == "symbol_retrieve":
            state = self._node_symbol_retrieve(state)
        else:
            state = self._node_hybrid_retrieve(state)

        # Step 3: Rerank
        state = self._node_rerank(state)

        # Step 4: Generate
        state = self._node_generate(state)

        return AgentResponse(
            question=state.get("question", question),
            answer=state.get("answer", "No answer generated."),
            sources=state.get("sources", []),
            citations=state.get("citations", []),
            tools_used=state.get("tools_used", []),
            query_type=state.get("query_type", ""),
            token_usage=state.get("token_usage", {}),
        )


def create_agent_graph(
    tools: AgentTools,
    retriever: Retriever,
    reranker: Optional[Reranker] = None,
    generator: Optional[AnswerGenerator] = None,
) -> AgentGraph:
    """Factory function to create an ``AgentGraph`` instance."""
    return AgentGraph(
        tools=tools,
        retriever=retriever,
        reranker=reranker,
        generator=generator,
    )
