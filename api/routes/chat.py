"""Chat routes for repository question answering."""

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter

from api.schemas import ChatRequest, ChatResponse
from src.services.chat_service import answer_question


router = APIRouter(tags=["chat"])


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
    )
