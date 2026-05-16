"""
Health check routes.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/")
async def root():
    return {
        "service": "Agentic RAG Codebase Assistant",
        "version": "1.0.0",
        "docs": "/docs",
    }
