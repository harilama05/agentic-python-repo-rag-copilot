"""Helpers for packaging grounded generation inputs.

This module keeps answer-generation context assembly separate from the agent so
future API and batch workflows can reuse the same grounding structure.
"""

from typing import Any, Dict, List


def build_generation_context(
    *,
    question: str,
    query_type: str,
    tools_used: List[str],
    raw_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a normalized generation payload from an agent response."""
    return {
        "question": question,
        "query_type": query_type,
        "tools_used": list(tools_used),
        "raw_results": dict(raw_results),
    }
