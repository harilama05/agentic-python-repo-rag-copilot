"""
Query router — classifies the user question and routes to the
appropriate pipeline path in the agent graph.
"""

from src.agent.state import AgentState
from src.agent.query_router import LLMQueryRouter, rule_based_fallback_route


def route_query(
    state: AgentState,
    query_router: LLMQueryRouter | None = None,
) -> AgentState:
    """
    Classify the user question and extract symbol candidates.

    This is the first node in the agent graph.
    """
    question = state["question"]

    if query_router:
        plan = query_router.route(question)
    else:
        plan = rule_based_fallback_route(question)

    state["query_type"] = plan.query_type
    state["symbol_candidate"] = plan.symbol
    state["rewritten_query"] = plan.rewritten_query
    state["router"] = plan.router
    state["router_confidence"] = plan.confidence
    state["router_reason"] = plan.reason
    state["tools_used"] = []
    state["search_results"] = []
    state["reranked_results"] = []
    state["citations"] = []
    state["sources"] = []
    state["token_usage"] = {}
    state["error"] = None

    return state


def should_use_symbol_search(state: AgentState) -> str:
    """
    Conditional edge: decides between symbol-first vs general search.

    Returns the name of the next node.
    """
    query_type = state.get("query_type", "search_query")
    symbol = state.get("symbol_candidate")

    if symbol and query_type in (
        "reference_query",
        "caller_query",
        "callee_query",
        "impact_query",
        "location_query",
        "explanation_query",
    ):
        return "symbol_retrieve"

    return "hybrid_retrieve"
