"""
Chat API routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    query_type: str
    tools_used: list
    sources: list
    citations: list


@router.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """Ask a question about the indexed codebase."""
    from api.routes_indexing import get_indexed_codebase

    indexed = get_indexed_codebase()
    if indexed is None:
        raise HTTPException(
            status_code=400,
            detail="No codebase indexed. Call POST /api/index/repository first.",
        )

    try:
        response = indexed.agent.invoke(request.question)

        return ChatResponse(
            question=response.question,
            answer=response.answer,
            query_type=response.query_type,
            tools_used=response.tools_used,
            sources=response.sources,
            citations=response.citations,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
