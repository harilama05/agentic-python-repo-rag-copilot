"""Routes for temporary GitHub and ZIP repository indexing."""

from uuid import uuid4

from fastapi import APIRouter, File, Form, Query, UploadFile

from api.schemas import (
    RepositorySessionResponse,
    TemporaryGithubRepoRequest,
    TemporaryRepoCleanupResponse,
)
from src.services.repository_service import (
    cleanup_temporary_repo,
    index_github_repo,
    index_zip_repo,
)


router = APIRouter(tags=["temporary-repositories"])


def _ensure_session_id(session_id: str | None) -> str:
    """Return caller-provided session_id or create a new API session id."""
    return session_id.strip() if session_id and session_id.strip() else str(uuid4())


def _serialize_repo(indexed, session_id: str) -> RepositorySessionResponse:
    """Serialize an IndexedCodebase into a stable API response."""
    text_count = getattr(indexed, "text_count", 0)
    json_count = getattr(indexed, "json_count", 0)
    docs_text_count = indexed.doc_count + text_count

    return RepositorySessionResponse(
        session_id=session_id,
        repo_id=indexed.repo_id,
        repo_name=indexed.repo_name,
        source_type=indexed.source_type,
        is_persistent=indexed.is_persistent,
        local_path=indexed.local_path,
        collection_name=indexed.collection_name,
        file_count=indexed.file_count,
        doc_count=indexed.doc_count,
        text_count=text_count,
        docs_text_count=docs_text_count,
        json_count=json_count,
        ignored_file_count=indexed.ignored_file_count,
        chunk_count=indexed.chunk_count,
        retrieval_mode=indexed.tools.retrieval_mode,
    )


@router.post(
    "/temporary-repos/github",
    response_model=RepositorySessionResponse,
)
def post_github_temporary_repo(
    request: TemporaryGithubRepoRequest,
) -> RepositorySessionResponse:
    """Clone and index a temporary public GitHub repository."""
    session_id = _ensure_session_id(request.session_id)

    indexed = index_github_repo(
        github_url=request.github_url,
        session_id=session_id,
        branch=request.branch,
        retrieval_mode=request.retrieval_mode,
        use_llm=request.use_llm,
        use_llm_router=request.use_llm_router,
    )

    return _serialize_repo(indexed, session_id=session_id)


@router.post(
    "/temporary-repos/zip",
    response_model=RepositorySessionResponse,
)
async def post_zip_temporary_repo(
    session_id: str | None = Form(None),
    retrieval_mode: str = Form("fast"),
    use_llm: bool = Form(True),
    use_llm_router: bool = Form(True),
    file: UploadFile = File(...),
) -> RepositorySessionResponse:
    """Index a temporary uploaded ZIP repository."""
    resolved_session_id = _ensure_session_id(session_id)
    zip_bytes = await file.read()

    indexed = index_zip_repo(
        filename=file.filename or "uploaded_repo.zip",
        zip_bytes=zip_bytes,
        session_id=resolved_session_id,
        retrieval_mode=retrieval_mode,
        use_llm=use_llm,
        use_llm_router=use_llm_router,
    )

    return _serialize_repo(indexed, session_id=resolved_session_id)


@router.delete(
    "/temporary-repos/{repo_id}",
    response_model=TemporaryRepoCleanupResponse,
)
def delete_temporary_repo(
    repo_id: str,
    session_id: str | None = Query(None),
) -> TemporaryRepoCleanupResponse:
    """Clean up one temporary repository and clear matching session state."""
    deleted = cleanup_temporary_repo(
        repo_id=repo_id,
        session_id=session_id,
    )

    return TemporaryRepoCleanupResponse(
        repo_id=repo_id,
        session_id=session_id,
        deleted=deleted,
    )
