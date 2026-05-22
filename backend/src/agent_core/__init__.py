"""Canonical agent package for runtime orchestration.

This package contains the main agent, tool façade, query router, and response
models used by the application. Legacy flat modules in `src/` re-export these
symbols for backward compatibility.
"""

from src.agent_core.agent import CodebaseAgent
from src.agent_core.query_router import LLMQueryRouter, QueryPlan
from src.agent_core.response_models import AgentResponse
from src.agent_core.tools import CodebaseTools

__all__ = [
    "AgentResponse",
    "CodebaseAgent",
    "CodebaseTools",
    "LLMQueryRouter",
    "QueryPlan",
]
