"""Chat routes for repository question answering."""

from fastapi import APIRouter

from api.schemas import ChatRequest, ChatResponse
from src.services.chat_service import answer_question


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def post_chat(request: ChatRequest) -> ChatResponse:
    """Answer a repository question for the caller's active session."""
    response = answer_question(
        session_id=request.session_id,
        question=request.question,
    )

    return ChatResponse(
        question=response.question,
        query_type=response.query_type,
        answer=response.answer,
        tools_used=response.tools_used,
        sources=response.sources,
        raw_results=response.raw_results,
    )
