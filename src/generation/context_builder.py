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
    Each chunk is clearly delimited with metadata and source code.
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

        # Build header with file location and symbol info
        header = f"### Source {i + 1}: `{relative_path}:{start_line}-{end_line}`"
        if qualified_name:
            header += f"\n**Type:** {symbol_type} | **Name:** `{qualified_name}`"

        chunk_text = result.text
        
        # Format as code block for better readability
        formatted_chunk = f"```python\n{chunk_text}\n```"

        # Truncate if adding this chunk would exceed max_chars
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(formatted_chunk) > remaining:
            formatted_chunk = formatted_chunk[:remaining] + "\n... (truncated)\n```"

        parts.append(f"{header}\n{formatted_chunk}")
        total_chars += len(formatted_chunk)

    return "\n\n---\n\n".join(parts)
