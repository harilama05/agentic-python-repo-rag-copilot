import json
import re
from dataclasses import dataclass
from typing import Optional

from src.constants import (
    QUERY_TYPE_CALLEE,
    QUERY_TYPE_CALLER,
    QUERY_TYPE_DOCUMENTATION,
    QUERY_TYPE_EXPLANATION,
    QUERY_TYPE_FLOW,
    QUERY_TYPE_IMPACT,
    QUERY_TYPE_LOCATION,
    QUERY_TYPE_REFERENCE,
    QUERY_TYPE_SEARCH,
)
from src.llm import GeminiLLM


ALLOWED_QUERY_TYPES = {
    QUERY_TYPE_DOCUMENTATION,
    QUERY_TYPE_LOCATION,
    QUERY_TYPE_REFERENCE,
    QUERY_TYPE_EXPLANATION,
    QUERY_TYPE_SEARCH,
    QUERY_TYPE_CALLER,
    QUERY_TYPE_CALLEE,
    QUERY_TYPE_IMPACT,
    QUERY_TYPE_FLOW,
}


@dataclass
class QueryPlan:
    query_type: str
    symbol: Optional[str]
    rewritten_query: str
    confidence: float
    reason: str
    router: str = "llm"


STOPWORDS = {
    "where", "is", "are", "the", "a", "an", "used", "use", "uses",
    "implemented", "defined", "located", "what", "does", "do",
    "explain", "how", "works", "work", "function", "class", "method",
    "in", "of", "to", "for", "and", "or", "with",

    "là", "gì", "làm", "để", "dùng", "được", "ở", "đâu",
    "giải", "thích", "hoạt", "động", "như", "thế", "nào",
    "chức", "năng", "có", "tác", "dụng",
}


ROUTER_SYSTEM_PROMPT = """
You are a query router for an Agentic RAG assistant that answers questions about Python repositories.

Your job is to classify the user's question into exactly one query type and extract a code symbol if present.

Allowed query types:

1. documentation_query
Use when the user asks about project purpose, README, setup, installation, tech stack, architecture, onboarding, roadmap, or project overview.

2. location_query
Use when the user asks where a function/class/method is implemented, defined, located, or declared.

3. reference_query
Use when the user asks where a symbol is used or referenced in the codebase.

4. explanation_query
Use when the user asks what a function/class/method does or how it works.

5. caller_query
Use when the user asks who calls a function/method/class, or what code depends on it as a caller.

6. callee_query
Use when the user asks what functions/methods are called by a function/method.

7. impact_query
Use when the user asks what may be affected if a symbol is changed, deleted, removed, renamed, or modified.

8. flow_query
Use when the user asks about execution flow, request flow, call chain, or how logic moves from one component to another.

9. search_query
Use for broad semantic search, feature search, or questions that do not fit the above types.

Symbol extraction rules:
- Extract symbol only if the question explicitly contains a concrete code symbol.
- Valid examples: create_user, create_task, UserService, TaskService.create_task.
- Do not invent symbols.
- Do not translate natural language into a guessed symbol.
- Do not set symbol to natural language phrases such as "task creation", "tạo task", "user creation", or "hàm tạo task".
- If the user describes a concept but does not mention an exact code symbol, set symbol to null.
- A symbol may be a function, class, method, or qualified method.

Return only valid JSON. Do not include markdown. Do not include explanations outside JSON.

JSON schema:
{
  "query_type": "one allowed query type",
  "symbol": "string or null",
  "rewritten_query": "clear English search query for retrieval",
  "confidence": 0.0,
  "reason": "brief reason"
}
"""


def extract_json_object(text: str) -> dict:
    """
    Extract the first JSON object from an LLM response.
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        raise ValueError(f"No JSON object found in router output: {text}")

    return json.loads(match.group(0))


def normalize_query_type(query_type: str) -> str:
    query_type = str(query_type).strip()

    if query_type in ALLOWED_QUERY_TYPES:
        return query_type

    return QUERY_TYPE_SEARCH


def normalize_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))

def is_valid_code_symbol(value: str | None) -> bool:
    if value is None:
        return False

    value = value.strip()

    if not value:
        return False

    pattern = r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"

    if re.match(pattern, value) is None:
        return False

    # Strong code-like signals:
    # - qualified symbol: TaskService.create_task
    # - snake_case: create_task
    # - CamelCase: TaskService
    if "." in value:
        return True

    if "_" in value:
        return True

    if any(ch.isupper() for ch in value[1:]):
        return True

    # Reject plain lowercase natural-language words like:
    # task, user, service, method, project
    return False

def extract_symbol_candidate(question: str) -> Optional[str]:
    """
    Fallback symbol extractor.

    Examples:
    - "Where is create_user used?" -> create_user
    - "What does UserService do?" -> UserService
    - "Who calls TaskService.create_task?" -> TaskService.create_task
    """
    backtick_match = re.search(r"`([^`]+)`", question)
    if backtick_match:
        return backtick_match.group(1).strip()

    tokens = re.findall(
        r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?\b",
        question,
    )

    candidates = []

    for token in tokens:
        lowered = token.lower()

        if lowered in STOPWORDS:
            continue

        score = 0

        if "." in token:
            score += 4

        if "_" in token:
            score += 3

        if any(ch.isupper() for ch in token[1:]):
            score += 2

        score += 1

        candidates.append((score, token))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def rule_based_fallback_route(question: str) -> QueryPlan:
    """
    Fallback only. The main pipeline should use LLMQueryRouter.
    This prevents the app from crashing if the LLM router fails.
    """
    q = question.lower()

    if any(phrase in q for phrase in [
        "được gọi bởi ai",
        "được gọi bởi",
        "gọi bởi ai",
        "gọi bởi",
        "ai gọi",
        "who calls",
        "callers",
        "called by",
    ]):
        query_type = QUERY_TYPE_CALLER

    elif any(phrase in q for phrase in [
        "gọi những hàm nào",
        "gọi hàm nào",
        "calls what",
        "callees",
        "what does it call",
    ]):
        query_type = QUERY_TYPE_CALLEE

    elif any(phrase in q for phrase in [
        "nếu xóa",
        "xóa",
        "nếu sửa",
        "sửa",
        "ảnh hưởng",
        "kéo theo",
        "impact",
        "affected",
        "what happens if",
    ]):
        query_type = QUERY_TYPE_IMPACT

    elif any(phrase in q for phrase in [
        "used",
        "called",
        "references",
        "referenced",
        "được dùng",
        "được sử dụng",
        "dùng ở đâu",
        "sử dụng ở đâu",
        "tham chiếu",
    ]):
        query_type = QUERY_TYPE_REFERENCE

    elif any(phrase in q for phrase in [
        "where is",
        "where are",
        "implemented",
        "defined",
        "located",
        "ở đâu",
        "nằm ở đâu",
        "định nghĩa ở đâu",
        "được implement",
    ]):
        query_type = QUERY_TYPE_LOCATION

    elif any(phrase in q for phrase in [
        "project",
        "repo",
        "repository",
        "overview",
        "setup",
        "install",
        "architecture",
        "tech stack",
        "onboarding",
        "readme",
        "purpose",
        "dự án",
        "tổng quan",
        "cài đặt",
        "cách chạy",
        "kiến trúc",
        "công nghệ",
        "intern mới",
        "người mới",
    ]):
        query_type = QUERY_TYPE_DOCUMENTATION

    elif any(phrase in q for phrase in [
        "what does",
        "explain",
        "how does",
        "how do",
        "làm gì",
        "để làm gì",
        "dùng để làm gì",
        "giải thích",
        "hoạt động như thế nào",
        "chức năng gì",
        "có tác dụng gì",
    ]):
        query_type = QUERY_TYPE_EXPLANATION

    else:
        query_type = QUERY_TYPE_SEARCH

    return QueryPlan(
        query_type=query_type,
        symbol=extract_symbol_candidate(question),
        rewritten_query=question,
        confidence=0.0,
        reason="Fallback rule-based routing because LLM router failed or was unavailable.",
        router="fallback_rule",
    )


class LLMQueryRouter:
    """
    Always routes the user's question through an LLM.

    Rule-based routing is used only as a technical fallback if the LLM fails.
    """

    def __init__(self, llm: GeminiLLM):
        self.llm = llm

    def route(self, question: str) -> QueryPlan:
        user_prompt = f"""
User question:
{question}

Return the query plan JSON now.
"""

        try:
            raw_output = self.llm.generate(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

            data = extract_json_object(raw_output)

            query_type = normalize_query_type(data.get("query_type", QUERY_TYPE_SEARCH))

            symbol = data.get("symbol")

            if symbol is not None:
                symbol = str(symbol).strip() or None

            # Reject natural-language phrases like "tạo task" or "task creation".
            if not is_valid_code_symbol(symbol):
                symbol = None

            # If the LLM forgot an obvious code-like symbol, recover it with regex.
            if symbol is None:
                fallback_symbol = extract_symbol_candidate(question)

                if is_valid_code_symbol(fallback_symbol):
                    symbol = fallback_symbol

            rewritten_query = str(
                data.get("rewritten_query") or question
            ).strip()

            confidence = normalize_confidence(data.get("confidence", 0.0))
            reason = str(data.get("reason") or "").strip()

            return QueryPlan(
                query_type=query_type,
                symbol=symbol,
                rewritten_query=rewritten_query,
                confidence=confidence,
                reason=reason,
                router="llm",
            )

        except Exception as exc:
            fallback = rule_based_fallback_route(question)
            fallback.reason = f"{fallback.reason} Router error: {exc}"
            return fallback