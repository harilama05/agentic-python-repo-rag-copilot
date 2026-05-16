"""
Agent state — defines the TypedDict that flows through the LangGraph.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

from src.schemas import SearchResult


class AgentState(TypedDict, total=False):
    """
    Mutable state carried through the agent graph.

    Each node reads from and writes to this dict.
    """
    # Input
    question: str

    # Classification
    query_type: str
    symbol_candidate: Optional[str]

    # Retrieval
    search_results: List[SearchResult]
    reranked_results: List[SearchResult]

    # Generation
    context: str
    answer: str
    citations: List[str]
    sources: List[Dict[str, Any]]

    # Tracking
    tools_used: List[str]
    token_usage: Dict[str, int]
    error: Optional[str]
