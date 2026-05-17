from typing import Any, Dict, List
import json

SYSTEM_PROMPT = """
You are an AI codebase assistant.

Your job is to answer questions about a Python repository using only the provided code, documentation, and graph context.

Rules:
1. Answer only using the provided context.
2. Do not invent files, functions, classes, project goals, setup steps, or behavior that are not shown in the context.
3. Do not include inline citations in the answer. The UI will show sources separately.
4. If graph_result is provided, use it for caller, callee, and impact analysis questions.
5. For caller_query, answer using graph_result["callers"] and explain the relationship using source_excerpts when available.
6. For callee_query, answer using graph_result["callees"] and explain the relationship using source_excerpts when available.
7. For impact_query, answer using graph_result["affected"] and explain why those nodes may be affected using source_excerpts when available.
8. Do not say information is unavailable if the relevant graph_result list contains entries.
9. If source_excerpts are provided, use them to explain concrete code behavior such as object creation, method calls, function calls, and return statements.
10. If the context is insufficient, say that you cannot determine the answer from the indexed repository.
11. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.
12. Keep the answer concise but useful.
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
    tools_used,
    raw_results,
) -> str:
    raw_results_json = json.dumps(
        raw_results,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    return f"""
Question:
{question}

Query type:
{query_type}

Tools used:
{tools_used}

Raw results:
{raw_results_json}

Graph result instructions:
If raw_results contains "graph_result", use it as structured graph evidence.

For caller_query:
- Use graph_result["targets"] as the target symbol.
- Use graph_result["callers"] to answer who calls the target.
- If graph_result["callers"] contains entries, do not say the caller cannot be determined.
- Use source_excerpts to explain how the caller calls the target.

For callee_query:
- Use graph_result["sources"] as the source symbol.
- Use graph_result["callees"] to answer what the source calls.
- If graph_result["callees"] contains entries, do not say the callees cannot be determined.
- Use source_excerpts to explain the calls with concrete code context.

For impact_query:
- Use graph_result["targets"] as the changed, removed, or modified symbol.
- Use graph_result["affected"] to answer what may be affected.
- If graph_result["affected"] contains entries, do not say the impact cannot be determined.
- Explain why each affected node may be impacted, using source_excerpts.

Source excerpt instructions:
- If raw_results contains "source_excerpts", use them to explain the relationship in more detail.
- Mention concrete behavior shown in the excerpt, such as object instantiation, function calls, method calls, return statements, or dependency relationships.
- Do not invent behavior that is not shown in the excerpts.

Your answer must:
- answer in the same language as the user's question
- be concise but useful
- explain the relevant code, documentation, or graph relationship clearly
- not include inline citations
- rely only on raw_results, graph_result, and source_excerpts
- mention uncertainty only if the relevant raw result list is empty
"""