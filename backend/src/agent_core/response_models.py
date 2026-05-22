"""Response models returned by the codebase agent.

These models are intentionally lightweight dataclasses so both Streamlit and
future API layers can serialize and display agent responses consistently.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class AgentResponse:
    """Structured answer returned by the codebase agent."""

    question: str
    query_type: str
    answer: str
    tools_used: List[str]
    sources: List[Dict[str, Any]]
    raw_results: Dict[str, Any]
