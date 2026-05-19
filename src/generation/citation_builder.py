"""
Citation builder — formats source references for the final answer.
"""

from typing import Any, Dict, List

from src.schemas import SearchResult


def build_citations(results: List[SearchResult]) -> List[str]:
    """
    Build human-readable citation strings from search results.

    Format: ``relative_path:start_line-end_line (symbol_type: qualified_name)``
    """
    citations: List[str] = []

    for result in results:
        meta = result.metadata
        relative_path = meta.get("relative_path", "unknown")
        start_line = meta.get("start_line", "?")
        end_line = meta.get("end_line", "?")
        qualified_name = meta.get("qualified_name", "")
        symbol_type = meta.get("symbol_type", "")

        if start_line == end_line:
            location = f"{relative_path}:{start_line}"
        else:
            location = f"{relative_path}:{start_line}-{end_line}"

        if qualified_name:
            citation = f"{location} ({symbol_type}: {qualified_name})"
        else:
            citation = location

        citations.append(citation)

    return citations


def build_source_dicts(results: List[SearchResult]) -> List[Dict[str, Any]]:
    """Build structured source dictionaries for the API response."""
    sources: List[Dict[str, Any]] = []

    for result in results:
        meta = result.metadata
        sources.append({
            "chunk_id": result.chunk_id,
            "relative_path": meta.get("relative_path", ""),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "symbol_name": meta.get("symbol_name", ""),
            "qualified_name": meta.get("qualified_name", ""),
            "symbol_type": meta.get("symbol_type", ""),
            "score": result.score,
        })

    return sources


def build_citations_from_sources(sources: List[Dict[str, Any]]) -> List[str]:
    """Build human-readable citation strings from graph/tool sources."""
    citations: List[str] = []

    for source in sources:
        relative_path = source.get("relative_path", "unknown")
        start_line = source.get("start_line") or source.get("line_number") or "?"
        end_line = source.get("end_line") or start_line
        qualified_name = source.get("qualified_name", "")
        symbol_type = source.get("symbol_type", "")

        if start_line == end_line:
            location = f"{relative_path}:{start_line}"
        else:
            location = f"{relative_path}:{start_line}-{end_line}"

        if qualified_name:
            citations.append(f"{location} ({symbol_type}: {qualified_name})")
        else:
            citations.append(location)

    return citations
