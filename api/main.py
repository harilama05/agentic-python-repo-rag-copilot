"""FastAPI application entrypoint.

This is a thin transport layer around the service modules. Business logic
remains inside `src.services`.
"""

from fastapi import FastAPI

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.repositories import router as repositories_router
from api.routes.temporary_repos import router as temporary_repos_router


app = FastAPI(title="Agentic Python Repo RAG Copilot API")
app.include_router(health_router)
app.include_router(repositories_router)
app.include_router(temporary_repos_router)
app.include_router(chat_router)
