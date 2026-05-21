"""Chat routes for repository question answering."""

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter

from api.schemas import ChatRequest, ChatResponse
from src.services.chat_service import answer_question


router = APIRouter(tags=["chat"])




LLM_ROUTER_WARNING = (
    "LLM Query Router is currently unavailable or rate-limited. "
    "The system is using the fallback rule-based router."
)

LLM_ANSWER_WARNING = (
    "LLM answer generation is currently unavailable or rate-limited. "
    "Showing the fallback tool/retrieval-based answer."
)


def _append_unique_warning(warnings: list[str], warning: str | None) -> None:
    """Append one clean warning message without duplicates."""
    if not warning:
        return

    clean_warning = str(warning).strip()

    if clean_warning and clean_warning not in warnings:
        warnings.append(clean_warning)


def _looks_like_llm_failure_text(value: str) -> bool:
    """Return True when a string appears to describe an LLM fallback/failure."""
    lower_value = value.lower()

    return (
        "llm" in lower_value
        and (
            "unavailable" in lower_value
            or "rate-limited" in lower_value
            or "rate limited" in lower_value
            or "fallback" in lower_value
            or "failed" in lower_value
            or "error" in lower_value
        )
    )


def _collect_warnings_from_value(value: Any, warnings: list[str]) -> None:
    """Recursively collect warning-like values from raw_results."""
    if value is None:
        return

    if isinstance(value, str):
        if _looks_like_llm_failure_text(value):
            if "router" in value.lower():
                _append_unique_warning(warnings, LLM_ROUTER_WARNING)
            elif "answer" in value.lower() or "generation" in value.lower():
                _append_unique_warning(warnings, LLM_ANSWER_WARNING)
            else:
                _append_unique_warning(warnings, value)
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_warnings_from_value(item, warnings)
        return

    if isinstance(value, dict):
        router_value = value.get("router")
        if isinstance(router_value, str) and router_value.startswith("fallback"):
            _append_unique_warning(warnings, LLM_ROUTER_WARNING)

        routers_value = value.get("routers")
        if isinstance(routers_value, list) and any(
            isinstance(router, str) and router.startswith("fallback")
            for router in routers_value
        ):
            _append_unique_warning(warnings, LLM_ROUTER_WARNING)

        router_error = value.get("router_error")
        router_errors = value.get("router_errors")
        if router_error or router_errors:
            _append_unique_warning(warnings, LLM_ROUTER_WARNING)

        if value.get("llm_error") or value.get("llm_warning"):
            _append_unique_warning(warnings, LLM_ANSWER_WARNING)

        if value.get("llm_enabled") is False and value.get("llm_error"):
            _append_unique_warning(warnings, LLM_ANSWER_WARNING)

        for key, item in value.items():
            key_lower = str(key).lower()

            # Do not scan source code or text excerpts for warnings
            if key_lower in {
                "source_excerpts",
                "search_results",
                "sources",
                "text",
                "content",
            }:
                continue

            if key_lower in {
                "warning",
                "warnings",
                "error",
                "errors",
                "fallback_reason",
                "router_error",
                "router_errors",
                "llm_warning",
                "llm_error",
            }:
                _collect_warnings_from_value(item, warnings)
            elif key_lower in {"router", "routers", "llm_enabled"}:
                continue
            else:
                _collect_warnings_from_value(item, warnings)


def extract_response_warnings(response: Any) -> list[str]:
    """Extract user-visible warning messages from an AgentResponse."""
    warnings: list[str] = []

    direct_warnings = getattr(response, "warnings", None)

    if isinstance(direct_warnings, str):
        _append_unique_warning(warnings, direct_warnings)
    elif isinstance(direct_warnings, list):
        for warning in direct_warnings:
            _append_unique_warning(warnings, str(warning))

    raw_results = getattr(response, "raw_results", None) or {}
    _collect_warnings_from_value(raw_results, warnings)

    if getattr(response, "router_fallback", False):
        _append_unique_warning(warnings, LLM_ROUTER_WARNING)

    if getattr(response, "answer_fallback", False) or getattr(response, "llm_failed", False):
        _append_unique_warning(warnings, LLM_ANSWER_WARNING)

    answer = getattr(response, "answer", "") or ""

    if "LLM Query Router is currently unavailable" in answer:
        _append_unique_warning(warnings, LLM_ROUTER_WARNING)

    if "LLM answer generation is currently unavailable" in answer:
        _append_unique_warning(warnings, LLM_ANSWER_WARNING)

    return warnings


def _json_safe(value: Any) -> Any:
    """Convert common Python objects into JSON-safe structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item)
            for item in value
        ]

    if is_dataclass(value):
        return _json_safe(asdict(value))

    return str(value)


@router.post("/chat", response_model=ChatResponse)
def post_chat(request: ChatRequest) -> ChatResponse:
    """Answer a repository question for the caller's active session."""
    response = answer_question(
        session_id=request.session_id,
        question=request.question,
    )

    return ChatResponse(
        session_id=request.session_id,
        question=response.question,
        query_type=response.query_type,
        answer=response.answer,
        tools_used=list(response.tools_used),
        sources=_json_safe(response.sources),
        raw_results=_json_safe(response.raw_results),
        warnings=extract_response_warnings(response),
    )
