"""
Context builder — assembles retrieved chunks into a structured context
string for the LLM prompt.
"""

from typing import List

from src.schemas import SearchResult


def build_context(
    results: List[SearchResult],
    max_chunks: int = 5,
    max_chars: int = 8000,
) -> str:
    """
    Build a context string from search results for the LLM.

    Limits total context size to avoid exceeding the LLM context window.
    Each chunk is clearly delimited with metadata.
    """
    if not results:
        return "(No relevant code found.)"

    parts: List[str] = []
    total_chars = 0

    for i, result in enumerate(results[:max_chunks]):
        relative_path = result.metadata.get("relative_path", "unknown")
        start_line = result.metadata.get("start_line", "?")
        end_line = result.metadata.get("end_line", "?")
        symbol_type = result.metadata.get("symbol_type", "")
        qualified_name = result.metadata.get("qualified_name", "")

        header = f"### Source {i + 1}: {relative_path}:{start_line}-{end_line}"
        if qualified_name:
            header += f" ({symbol_type}: {qualified_name})"

        chunk_text = result.text

        # Truncate if adding this chunk would exceed max_chars
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(chunk_text) > remaining:
            chunk_text = chunk_text[:remaining] + "\n... (truncated)"

        parts.append(f"{header}\n{chunk_text}")
        total_chars += len(chunk_text)

    return "\n\n---\n\n".join(parts)
