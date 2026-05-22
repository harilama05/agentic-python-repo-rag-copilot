"""LLM and fallback query routing for agent requests.

This module preserves the existing routing and planning behavior while moving
the canonical implementation into a non-conflicting package.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from src.core.constants import (
    QUERY_TYPE_CALLEE,
    QUERY_TYPE_CALLER,
    QUERY_TYPE_DOCUMENTATION,
    QUERY_TYPE_EXPLANATION,
    QUERY_TYPE_FLOW,
    QUERY_TYPE_IMPACT,
    QUERY_TYPE_LOCATION,
    QUERY_TYPE_REFERENCE,
    QUERY_TYPE_SEARCH,
    QUERY_TYPE_COUNT,
)
from src.generation.llm import GeminiLLM


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
    QUERY_TYPE_COUNT,
}


@dataclass
class QueryPlan:
    """Structured routing decision for one sub-question."""

    query_type: str
    symbol: Optional[str]
    rewritten_query: str
    confidence: float
    reason: str
    router: str = "llm"
    router_error: Optional[str] = None


STOPWORDS = {
    "where", "is", "are", "the", "a", "an", "used", "use", "uses",
    "implemented", "defined", "located", "what", "does", "do",
    "explain", "how", "works", "work", "function", "class", "method",
    "in", "of", "to", "for", "and", "or", "with",
    "la", "gi", "lam", "de", "dung", "duoc", "o", "dau",
    "giai", "thich", "hoat", "dong", "nhu", "the", "nao",
    "chuc", "nang", "co", "tac", "dung",
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

10. count_query
Use when the user asks how many of a specific type exist (e.g., "how many functions", "how many classes", "how many files", "how many Python files", "có mấy hàm", "có bao nhiêu class", "có bao nhiêu file python", "liệt kê file", "list files"). Set symbol to the type requested.

Symbol extraction rules:
- Extract symbol only if the question explicitly contains a concrete code symbol.
- Valid examples: create_user, create_task, UserService, TaskService.create_task.
- For count_query, set symbol to exactly one of "function", "class", "method", "file", "python_file", "all_files", or "all".
  - Use "file" or "python_file" when the user asks about Python files specifically.
  - Use "all_files" when the user asks about all files in the repo.
  - Use "function", "class", "method" when asking about code symbols.
  - Use "all" when asking about all symbols generically.
- Do not invent symbols.
- Do not translate natural language into a guessed symbol.
- Do not set symbol to natural language phrases such as "task creation", "tao task", "user creation", or "ham tao task".
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


PLANNER_SYSTEM_PROMPT = """
You are an LLM Query Planner for an Agentic RAG assistant that answers questions about Python repositories.

Your job is to decompose the user's question into one or more concrete query plans.

Allowed query_type values:
- documentation_query: questions about README, project purpose, setup, usage, architecture overview
- location_query: where a symbol/function/class/method is defined or implemented
- explanation_query: what a symbol/function/class/method does, its purpose, behavior, or responsibility
- reference_query: where a symbol is referenced or used
- caller_query: who calls a function/method
- callee_query: what a function/method calls
- impact_query: what may be affected if a symbol changes
- flow_query: execution flow, request flow, call chain, or how logic moves through components
- count_query: how many functions/classes/methods/files exist, or list files
- search_query: general semantic code search

Rules:
1. Always return a JSON object with a "plans" list.
2. If the user asks one thing, return exactly one plan.
3. If the user asks multiple things, return multiple plans.
4. If the user asks "where is X and what does X do", return:
   - location_query for X
   - explanation_query for X
5. If the user asks "who calls X and what is affected if X changes", return:
   - caller_query for X
   - impact_query for X
6. If the user asks "where is X used and where is X defined", return:
   - reference_query for X
   - location_query for X
7. Use symbol only when there is a concrete code symbol.
8. Do not invent symbols.
9. Do not translate natural language descriptions into guessed code symbols.
10. Return valid JSON only. Do not include markdown fences.

JSON schema:
{
  "plans": [
    {
      "query_type": "location_query",
      "symbol": "ModelEvaluator",
      "rewritten_query": "Where is ModelEvaluator defined?",
      "confidence": 0.95,
      "reason": "The user asks where ModelEvaluator is defined."
    }
  ]
}
"""


def extract_json_object(text: str) -> dict:
    """Extract the first JSON object from a model response."""
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text)
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
    """Normalize model output query types to allowed values."""
    query_type = str(query_type).strip()

    if query_type in ALLOWED_QUERY_TYPES:
        return query_type

    return QUERY_TYPE_SEARCH


def normalize_confidence(value: object) -> float:
    """Normalize confidence values to the [0, 1] range."""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))


def is_valid_code_symbol(value: str | None) -> bool:
    """Return True if a string looks like a concrete code symbol."""
    if value is None:
        return False

    value = value.strip()

    if not value:
        return False

    pattern = r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"

    if re.match(pattern, value) is None:
        return False

    if value in {"function", "class", "method", "all", "file", "python_file", "all_files"}:
        return True

    if "." in value:
        return True

    if "_" in value:
        return True

    if any(ch.isupper() for ch in value[1:]):
        return True

    return False


def extract_symbol_candidate(question: str) -> Optional[str]:
    """Extract the most code-like symbol candidate from free text."""
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


def _normalize_text_for_matching(text: str) -> str:
    """Normalize free text for accent-insensitive fallback matching."""
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def normalize_symbol(
    raw_symbol: object,
    *,
    question: str,
    rewritten_query: str | None = None,
) -> Optional[str]:
    """Normalize and validate a symbol returned by the planner/router."""
    symbol = raw_symbol

    if symbol is not None:
        symbol = str(symbol).strip() or None

    if not is_valid_code_symbol(symbol):
        symbol = None

    if symbol is None and rewritten_query:
        fallback_symbol = extract_symbol_candidate(rewritten_query)

        if is_valid_code_symbol(fallback_symbol):
            symbol = fallback_symbol

    if symbol is None:
        fallback_symbol = extract_symbol_candidate(question)

        if is_valid_code_symbol(fallback_symbol):
            symbol = fallback_symbol

    return symbol


def build_query_plan_from_data(
    data: dict,
    *,
    question: str,
    router: str,
) -> QueryPlan:
    """Convert normalized planner data into a QueryPlan."""
    query_type = normalize_query_type(data.get("query_type", QUERY_TYPE_SEARCH))
    rewritten_query = str(data.get("rewritten_query") or question).strip()
    symbol = normalize_symbol(
        data.get("symbol"),
        question=question,
        rewritten_query=rewritten_query,
    )
    confidence = normalize_confidence(data.get("confidence", 0.0))
    reason = str(data.get("reason") or "").strip()

    router_error = data.get("router_error")
    if router_error is not None:
        router_error = str(router_error)

    return QueryPlan(
        query_type=query_type,
        symbol=symbol,
        rewritten_query=rewritten_query,
        confidence=confidence,
        reason=reason,
        router=router,
        router_error=router_error,
    )


def rule_based_fallback_route(question: str) -> QueryPlan:
    """Route a query using deterministic fallback rules."""
    q = _normalize_text_for_matching(question)

    if any(phrase in q for phrase in [
        "duoc goi boi ai",
        "duoc goi boi",
        "goi boi ai",
        "goi boi",
        "ai goi",
        "who calls",
        "callers",
        "called by",
    ]):
        query_type = QUERY_TYPE_CALLER
    elif any(phrase in q for phrase in [
        "goi nhung ham nao",
        "goi ham nao",
        "calls what",
        "callees",
        "what does it call",
    ]):
        query_type = QUERY_TYPE_CALLEE
    elif any(phrase in q for phrase in [
        "neu xoa",
        "xoa",
        "neu sua",
        "sua",
        "anh huong",
        "keo theo",
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
        "duoc dung",
        "duoc su dung",
        "dung o dau",
        "su dung o dau",
        "tham chieu",
    ]):
        query_type = QUERY_TYPE_REFERENCE
    elif any(phrase in q for phrase in [
        "where is",
        "where are",
        "implemented",
        "defined",
        "located",
        "o dau",
        "nam o dau",
        "dinh nghia o dau",
        "duoc implement",
        "duoc tao o dau",
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
        "du an",
        "tong quan",
        "cai dat",
        "cach chay",
        "kien truc",
        "cong nghe",
        "intern moi",
        "nguoi moi",
    ]):
        query_type = QUERY_TYPE_DOCUMENTATION
    elif any(phrase in q for phrase in [
        "what does",
        "explain",
        "how does",
        "how do",
        "lam gi",
        "de lam gi",
        "dung de lam gi",
        "muc dich",
        "giai thich",
        "hoat dong nhu the nao",
        "chuc nang gi",
        "co tac dung gi",
    ]):
        query_type = QUERY_TYPE_EXPLANATION
    elif any(phrase in q for phrase in [
        "flow",
        "request flow",
        "execution flow",
        "call chain",
        "luong",
        "quy trinh",
    ]):
        query_type = QUERY_TYPE_FLOW
    elif any(phrase in q for phrase in [
        "how many",
        "count",
        "co may",
        "co bao nhieu",
        "so luong",
        "liet ke",
        "list all",
        "list file",
        "list the file",
    ]):
        query_type = QUERY_TYPE_COUNT
        # Determine if user asks about files or symbols
        symbol = "all"
        if any(w in q for w in ["file", "tap tin"]):
            if any(w in q for w in ["python", ".py"]):
                symbol = "python_file"
            else:
                symbol = "file"
        elif "function" in q or "ham" in q:
            symbol = "function"
        elif "class" in q or "lop" in q:
            symbol = "class"
        elif "method" in q or "phuong thuc" in q:
            symbol = "method"
        
        return QueryPlan(
            query_type=query_type,
            symbol=symbol,
            rewritten_query=question,
            confidence=0.0,
            reason="Fallback rule-based routing for counting.",
            router="fallback_rule",
        )
    else:
        query_type = QUERY_TYPE_SEARCH

    return QueryPlan(
        query_type=query_type,
        symbol=extract_symbol_candidate(question),
        rewritten_query=question,
        confidence=0.0,
        reason="Fallback rule-based routing because LLM router/planner failed or was unavailable.",
        router="fallback_rule",
    )


class LLMQueryRouter:
    """Main query planner used by the agent runtime."""

    def __init__(self, llm: Optional[GeminiLLM] = None):
        self.llm = llm

    def route(self, question: str) -> QueryPlan:
        """Return a single routing plan, preserving legacy behavior."""
        if self.llm is None:
            fallback = rule_based_fallback_route(question)
            fallback.router_error = "LLM router is unavailable; using fallback rules."
            return fallback

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

            return build_query_plan_from_data(
                data,
                question=question,
                router="llm",
            )

        except Exception as exc:
            fallback = rule_based_fallback_route(question)
            fallback.reason = f"{fallback.reason} Router error: {exc}"
            fallback.router_error = str(exc)
            return fallback

    def route_many(self, question: str) -> list[QueryPlan]:
        """Return one or more query plans for multi-intent questions."""
        if self.llm is None:
            fallback = rule_based_fallback_route(question)
            fallback.router_error = "LLM planner is unavailable; using fallback rules."
            return [fallback]

        user_prompt = f"""
User question:
{question}

Return the query plans JSON now.
"""

        try:
            raw_output = self.llm.generate(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

            data = extract_json_object(raw_output)
            raw_plans = data.get("plans", [])

            if not isinstance(raw_plans, list) or not raw_plans:
                return [self.route(question)]

            plans: list[QueryPlan] = []

            for item in raw_plans[:4]:
                if not isinstance(item, dict):
                    continue

                plan = build_query_plan_from_data(
                    item,
                    question=question,
                    router="llm_planner",
                )

                plans.append(plan)

            if not plans:
                return [self.route(question)]

            deduped: list[QueryPlan] = []
            seen = set()

            for plan in plans:
                key = (
                    plan.query_type,
                    plan.symbol or "",
                    plan.rewritten_query or "",
                )

                if key in seen:
                    continue

                seen.add(key)
                deduped.append(plan)

            return deduped

        except Exception as exc:
            fallback = self.route(question)
            fallback.reason = f"{fallback.reason} Planner error: {exc}"
            return [fallback]
