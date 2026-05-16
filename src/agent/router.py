"""
Query router — classifies the user question and routes to the
appropriate pipeline path in the agent graph.
"""

from src.agent.state import AgentState
from src.retrieval.query_transform import classify_query, extract_symbol_candidate


def route_query(state: AgentState) -> AgentState:
    """
    Classify the user question and extract symbol candidates.

    This is the first node in the agent graph.
    """
    question = state["question"]

    state["query_type"] = classify_query(question)
    state["symbol_candidate"] = extract_symbol_candidate(question)
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

    if symbol and query_type in ("reference_query", "location_query", "explanation_query"):
        return "symbol_retrieve"

    return "hybrid_retrieve"
