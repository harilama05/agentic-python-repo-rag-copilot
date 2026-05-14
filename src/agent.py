import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.llm import GeminiLLM
from src.prompts import SYSTEM_PROMPT, build_grounded_user_prompt
from src.tools import CodebaseTools


@dataclass
class AgentResponse:
    question: str
    query_type: str
    answer: str
    tools_used: List[str]
    sources: List[Dict[str, Any]]
    raw_results: Dict[str, Any]


STOPWORDS = {
    "where", "is", "are", "the", "a", "an", "used", "use", "uses",
    "implemented", "defined", "located", "what", "does", "do",
    "explain", "how", "works", "work", "function", "class", "method",
    "in", "of", "to", "for", "and", "or", "with",
}


def classify_query(question: str) -> str:
    q = question.lower()

    if any(phrase in q for phrase in ["used", "called", "references", "referenced"]):
        return "reference_query"

    if any(phrase in q for phrase in ["where is", "where are", "implemented", "defined", "located"]):
        return "location_query"

    if any(phrase in q for phrase in ["what does", "explain", "how does", "how do"]):
        return "explanation_query"

    return "search_query"


def extract_symbol_candidate(question: str) -> Optional[str]:
    """
    Extract likely symbol name from a natural language question.

    Examples:
    - "Where is create_user used?" -> create_user
    - "What does UserService do?" -> UserService
    """

    # Prefer symbol inside backticks.
    backtick_match = re.search(r"`([^`]+)`", question)
    if backtick_match:
        return backtick_match.group(1).strip()

    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", question)

    candidates = []

    for token in tokens:
        lowered = token.lower()

        if lowered in STOPWORDS:
            continue

        score = 0

        # snake_case usually indicates Python symbol.
        if "_" in token:
            score += 3

        # CamelCase likely class name.
        if any(ch.isupper() for ch in token[1:]):
            score += 2

        # Non-stopword token still possible.
        score += 1

        candidates.append((score, token))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


class CodebaseAgent:
    def __init__(
        self,
        tools: CodebaseTools,
        llm: Optional[GeminiLLM] = None,
        use_llm: bool = False,
    ):
        self.tools = tools
        self.llm = llm
        self.use_llm = use_llm

    def answer(self, question: str) -> AgentResponse:
        query_type = classify_query(question)
        symbol = extract_symbol_candidate(question)

        if query_type == "reference_query" and symbol:
            response = self._answer_reference_query(question, symbol)

        elif query_type == "location_query" and symbol:
            response = self._answer_location_query(question, symbol)

        elif query_type == "explanation_query" and symbol:
            response = self._answer_explanation_query(question, symbol)

        else:
            response = self._answer_search_query(question)

        return self._maybe_generate_llm_answer(response)

    def _maybe_generate_llm_answer(self, response: AgentResponse) -> AgentResponse:
        """
        Replace the rule-based answer with an LLM-generated grounded answer
        when LLM generation is enabled.
        """
        if not self.use_llm or self.llm is None:
            return response

        try:
            user_prompt = build_grounded_user_prompt(
                question=response.question,
                query_type=response.query_type,
                tools_used=response.tools_used,
                raw_results=response.raw_results,
            )

            llm_answer = self.llm.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

            response.answer = llm_answer
            response.raw_results["llm_enabled"] = True

            return response

        except Exception as exc:
            response.raw_results["llm_enabled"] = False
            response.raw_results["llm_error"] = str(exc)

            response.answer = (
                response.answer
                + "\n\n"
                + f"LLM answer generation failed: {exc}"
            )

            return response

    def _answer_reference_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_references("{symbol}")']
        references = self.tools.find_references(symbol)

        if not references:
            answer = f"I could not find any references to `{symbol}` in the indexed codebase."
            return AgentResponse(
                question=question,
                query_type="reference_query",
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"references": references},
            )

        lines = [f"I found `{symbol}` in these locations:"]

        sources = []

        for ref in references:
            line_type = "definition" if ref["is_definition"] else "reference"
            lines.append(
                f"- `{ref['relative_path']}:{ref['line_number']}` "
                f"({line_type}) — `{ref['line'].strip()}`"
            )

            sources.append(
                {
                    "relative_path": ref["relative_path"],
                    "line_start": ref["line_number"],
                    "line_end": ref["line_number"],
                    "type": line_type,
                }
            )

        return AgentResponse(
            question=question,
            query_type="reference_query",
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"references": references},
        )

    def _answer_location_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_symbol("{symbol}")']
        symbol_results = self.tools.find_symbol(symbol)

        if not symbol_results:
            tools_used.append(f'search_code("{question}")')
            search_results = self.tools.search_code(question, top_k=3)

            if not search_results:
                answer = f"I could not find `{symbol}` in the indexed codebase."
                return AgentResponse(
                    question=question,
                    query_type="location_query",
                    answer=answer,
                    tools_used=tools_used,
                    sources=[],
                    raw_results={"symbol_results": [], "search_results": []},
                )

            lines = [f"I could not find an exact symbol match for `{symbol}`, but found related code:"]
            sources = []

            for result in search_results:
                lines.append(
                    f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                    f"— `{result['qualified_name']}` ({result['symbol_type']})"
                )

                sources.append(
                    {
                        "relative_path": result["relative_path"],
                        "line_start": result["start_line"],
                        "line_end": result["end_line"],
                        "symbol": result["qualified_name"],
                    }
                )

            return AgentResponse(
                question=question,
                query_type="location_query",
                answer="\n".join(lines),
                tools_used=tools_used,
                sources=sources,
                raw_results={
                    "symbol_results": symbol_results,
                    "search_results": search_results,
                },
            )

        lines = [f"`{symbol}` is defined in:"]
        sources = []

        for result in symbol_results:
            lines.append(
                f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                f"— `{result['qualified_name']}` ({result['symbol_type']})"
            )

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": result["qualified_name"],
                }
            )

        return AgentResponse(
            question=question,
            query_type="location_query",
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"symbol_results": symbol_results},
        )

    def _answer_explanation_query(self, question: str, symbol: str) -> AgentResponse:
        tools_used = [f'find_symbol("{symbol}")']
        symbol_results = self.tools.find_symbol(symbol)

        if not symbol_results:
            return self._answer_search_query(question)

        first = symbol_results[0]

        tools_used.append(
            f"read_file({first['relative_path']}, "
            f"{first['start_line']}, {first['end_line']})"
        )

        file_content = self.tools.read_file(
            file_path=first["relative_path"],
            start_line=first["start_line"],
            end_line=first["end_line"],
            context_lines=0,
        )

        answer = (
            f"`{first['qualified_name']}` is a `{first['symbol_type']}` defined in "
            f"`{first['relative_path']}:{first['start_line']}-{first['end_line']}`.\n\n"
            f"Code excerpt:\n"
            f"```python\n{file_content['content']}\n```"
        )

        sources = [
            {
                "relative_path": first["relative_path"],
                "line_start": first["start_line"],
                "line_end": first["end_line"],
                "symbol": first["qualified_name"],
            }
        ]

        return AgentResponse(
            question=question,
            query_type="explanation_query",
            answer=answer,
            tools_used=tools_used,
            sources=sources,
            raw_results={
                "symbol_results": symbol_results,
                "file_content": file_content,
            },
        )

    def _answer_search_query(self, question: str) -> AgentResponse:
        tools_used = [f'search_code("{question}")']
        search_results = self.tools.search_code(question, top_k=5)

        if not search_results:
            answer = "I could not find relevant code in the indexed codebase."
            return AgentResponse(
                question=question,
                query_type="search_query",
                answer=answer,
                tools_used=tools_used,
                sources=[],
                raw_results={"search_results": []},
            )

        lines = ["I found these relevant code locations:"]
        sources = []

        for result in search_results:
            lines.append(
                f"- `{result['relative_path']}:{result['start_line']}-{result['end_line']}` "
                f"— `{result['qualified_name']}` ({result['symbol_type']})"
            )

            sources.append(
                {
                    "relative_path": result["relative_path"],
                    "line_start": result["start_line"],
                    "line_end": result["end_line"],
                    "symbol": result["qualified_name"],
                }
            )

        return AgentResponse(
            question=question,
            query_type="search_query",
            answer="\n".join(lines),
            tools_used=tools_used,
            sources=sources,
            raw_results={"search_results": search_results},
        )