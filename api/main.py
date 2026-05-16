"""
FastAPI application — assembles all route modules.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_health import router as health_router
from api.routes_indexing import router as indexing_router
from api.routes_upload import router as upload_router
from api.routes_chat import router as chat_router

app = FastAPI(
    title="Agentic RAG Codebase Assistant",
    description="REST API for indexing Python codebases and answering questions.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(indexing_router)
app.include_router(upload_router)
app.include_router(chat_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
