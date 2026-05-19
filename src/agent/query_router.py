"""
LLM-first query router with deterministic rule-based fallback.

The router returns one QueryPlan for the current agent graph. The graph can
still use the old rule-based classifier when no LLM is configured or when the
LLM output is not valid JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import openai

from src.config import settings
from src.retrieval.query_transform import classify_query, extract_symbol_candidate


ALLOWED_QUERY_TYPES = {
    "documentation_query",
    "location_query",
    "reference_query",
    "caller_query",
    "callee_query",
    "impact_query",
    "flow_query",
    "explanation_query",
    "search_query",
}

@dataclass
class QueryPlan:
    query_type: str
    symbol: Optional[str]
    rewritten_query: str
    confidence: float
    reason: str
    router: str = "fallback_rule"


ROUTER_SYSTEM_PROMPT = """
You are a query router for an Agentic RAG assistant that answers questions about Python repositories.

Classify the user's question into exactly one query type and extract a concrete code symbol only if present.

Allowed query types:
- documentation_query: README, setup, usage, tech stack, architecture overview, project purpose.
- location_query: where a function/class/method is defined, implemented, located, or declared.
- reference_query: where a symbol is used or referenced.
- caller_query: who calls a function/method/class, or what code depends on it as a caller.
- callee_query: what functions/methods are called by a function/method.
- impact_query: what may be affected if a symbol is changed, deleted, removed, renamed, or modified.
- flow_query: execution flow, request flow, call chain, or how logic moves between components.
- explanation_query: what a function/class/method does or how it works.
- search_query: broad semantic search or questions that do not fit the above types.

Symbol extraction rules:
- Extract symbol only if the question explicitly contains a concrete code symbol.
- Valid examples: create_user, UserService, TaskService.create_task.
- Do not invent symbols.
- Do not translate natural language into a guessed symbol.
- If no exact code symbol appears, use null.

Return only valid JSON:
{
  "query_type": "one allowed query type",
  "symbol": "string or null",
  "rewritten_query": "clear search query for retrieval",
  "confidence": 0.0,
  "reason": "brief reason"
}
"""


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in router output: {text}")

    return json.loads(match.group(0))


def normalize_query_type(value: object) -> str:
    query_type = str(value or "").strip()
    if query_type not in ALLOWED_QUERY_TYPES:
        return "search_query"
    return query_type


def normalize_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def is_valid_code_symbol(value: object) -> bool:
    if value is None:
        return False

    symbol = str(value).strip()
    if not symbol:
        return False

    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$", symbol) is None:
        return False

    # Avoid accepting plain natural-language lowercase words as symbols.
    return "." in symbol or "_" in symbol or any(ch.isupper() for ch in symbol)


def normalize_symbol(
    raw_symbol: object,
    *,
    question: str,
    rewritten_query: str,
) -> Optional[str]:
    symbol = str(raw_symbol).strip() if raw_symbol is not None else None
    if is_valid_code_symbol(symbol):
        return symbol

    for text in (rewritten_query, question):
        fallback = extract_symbol_candidate(text)
        if is_valid_code_symbol(fallback):
            return fallback

    return None


def rule_based_fallback_route(question: str, reason: str = "") -> QueryPlan:
    return QueryPlan(
        query_type=classify_query(question),
        symbol=extract_symbol_candidate(question),
        rewritten_query=question,
        confidence=0.0,
        reason=reason or "Fallback rule-based routing.",
        router="fallback_rule",
    )


class LLMQueryRouter:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.llm_model
        self._base_url = base_url
        self._client = None
        if self._api_key:
            self._client = openai.OpenAI(api_key=self._api_key, base_url=base_url)

    def route(self, question: str) -> QueryPlan:
        if self._client is None:
            return rule_based_fallback_route(
                question,
                reason="LLM router unavailable because no API key is configured.",
            )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"User question:\n{question}"},
                ],
                temperature=0.0,
                max_tokens=400,
            )
            raw_output = response.choices[0].message.content or ""
            data = extract_json_object(raw_output)

            query_type = normalize_query_type(data.get("query_type"))
            rewritten_query = str(data.get("rewritten_query") or question).strip()
            symbol = normalize_symbol(
                data.get("symbol"),
                question=question,
                rewritten_query=rewritten_query,
            )

            return QueryPlan(
                query_type=query_type,
                symbol=symbol,
                rewritten_query=rewritten_query,
                confidence=normalize_confidence(data.get("confidence")),
                reason=str(data.get("reason") or "").strip(),
                router="llm",
            )

        except Exception as exc:
            return rule_based_fallback_route(
                question,
                reason=f"Fallback rule-based routing because LLM router failed: {exc}",
            )
