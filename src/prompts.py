from typing import Any, Dict, List


SYSTEM_PROMPT = """
You are an AI codebase assistant.

Your job is to answer questions about a Python codebase using only the provided code context.

Rules:
1. Answer only using the provided context.
2. Do not invent files, functions, classes, or behavior that are not shown in the context.
3. Cite file paths and line numbers when explaining code.
4. If the context is insufficient, say that you cannot determine the answer from the indexed codebase.
5. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.
6. Keep the answer concise but useful.
7. Use citations in this format: `path/to/file.py:start-end`.
8. Do not put citations inside quotes or brackets unless necessary.
"""


def _truncate(text: str, max_chars: int = 2500) -> str:
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n... [truncated]"


def _format_tool_list(tools_used: List[str]) -> str:
    if not tools_used:
        return "No tools used."

    return "\n".join(f"- {tool}" for tool in tools_used)


def _format_references(references: List[Dict[str, Any]]) -> str:
    if not references:
        return ""

    blocks = ["Reference search results:"]

    for ref in references:
        relative_path = ref.get("relative_path")
        line_number = ref.get("line_number")
        line = ref.get("line", "").strip()
        is_definition = ref.get("is_definition")

        ref_type = "definition" if is_definition else "reference"

        blocks.append(
            f"[Source: {relative_path}:{line_number} | {ref_type}]\n"
            f"{line}"
        )

    return "\n\n".join(blocks)


def _format_code_results(results: List[Dict[str, Any]], title: str) -> str:
    if not results:
        return ""

    blocks = [title]

    for result in results:
        relative_path = result.get("relative_path")
        start_line = result.get("start_line")
        end_line = result.get("end_line")
        qualified_name = result.get("qualified_name")
        symbol_type = result.get("symbol_type")
        text = result.get("text", "")

        blocks.append(
            f"[Source: {relative_path}:{start_line}-{end_line}]\n"
            f"Symbol: {qualified_name}\n"
            f"Type: {symbol_type}\n"
            f"{_truncate(text)}"
        )

    return "\n\n".join(blocks)


def _format_file_content(file_content: Dict[str, Any]) -> str:
    if not file_content:
        return ""

    relative_path = file_content.get("relative_path")
    start_line = file_content.get("start_line")
    end_line = file_content.get("end_line")
    content = file_content.get("content", "")

    return (
        "File content:\n\n"
        f"[Source: {relative_path}:{start_line}-{end_line}]\n"
        f"```python\n{_truncate(content)}\n```"
    )


def build_grounded_user_prompt(
    question: str,
    query_type: str,
    tools_used: List[str],
    raw_results: Dict[str, Any],
) -> str:
    context_parts = []

    references = raw_results.get("references", [])
    if references:
        context_parts.append(_format_references(references))

    symbol_results = raw_results.get("symbol_results", [])
    if symbol_results:
        context_parts.append(
            _format_code_results(
                symbol_results,
                title="Symbol lookup results:",
            )
        )

    search_results = raw_results.get("search_results", [])
    if search_results:
        context_parts.append(
            _format_code_results(
                search_results,
                title="Code search results:",
            )
        )

    file_content = raw_results.get("file_content", {})
    if file_content:
        context_parts.append(_format_file_content(file_content))

    if not context_parts:
        context_text = "No code context was retrieved."
    else:
        context_text = "\n\n---\n\n".join(context_parts)

    return f"""
User question:
{question}

Query type:
{query_type}

Tools used:
{_format_tool_list(tools_used)}

Retrieved code context:
{context_text}

Task:
Write a grounded answer to the user's question using only the retrieved code context.

Your answer must:
- explain the relevant code clearly
- cite file paths and line numbers
- mention uncertainty if the retrieved context is insufficient
"""