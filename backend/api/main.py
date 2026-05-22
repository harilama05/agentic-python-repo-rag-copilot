"""FastAPI application entrypoint.

This module only owns HTTP transport concerns:
- application assembly
- CORS configuration
- route registration
- centralized API error handling

Business logic stays in src.services.
"""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.repositories import router as repositories_router
from api.routes.temporary_repos import router as temporary_repos_router
from src.observability.logger import configure_logging, get_logger


configure_logging()
logger = get_logger(__name__)


def _get_cors_origins() -> list[str]:
    """Return allowed CORS origins from env or safe local defaults."""
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()

    if raw_origins:
        return [
            origin.strip()
            for origin in raw_origins.split(",")
            if origin.strip()
        ]

    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


app = FastAPI(
    title="Agentic Python Repo RAG Copilot API",
    version="0.1.0",
    description=(
        "FastAPI backend for loading/indexing repositories and answering "
        "codebase questions with Agentic RAG."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return clean 400 responses for expected service-layer validation errors."""
    logger.warning(
        "API value error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
        },
    )

    return JSONResponse(
        status_code=400,
        content={
            "error": "bad_request",
            "detail": str(exc),
        },
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(
    request: Request,
    exc: FileNotFoundError,
) -> JSONResponse:
    """Return clean 404 responses for missing local repository/file resources."""
    logger.warning(
        "API file not found",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
        },
    )

    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "detail": str(exc),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Log and return explicit HTTP exceptions."""
    logger.warning(
        "API HTTP exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": exc.detail,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return clean 500 responses without leaking tracebacks to the frontend."""
    logger.exception(
        "Unhandled API error",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected server error occurred.",
        },
    )


app.include_router(health_router)
app.include_router(repositories_router)
app.include_router(temporary_repos_router)
app.include_router(chat_router)


logger.info("FastAPI application configured")
