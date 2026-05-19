"""Routes for temporary GitHub and ZIP repository indexing."""

from fastapi import APIRouter, File, Form, UploadFile

from api.schemas import TemporaryGithubRepoRequest, TemporaryRepoCleanupResponse, TemporaryRepoResponse
from src.services.repository_service import cleanup_temporary_repo, index_github_repo, index_zip_repo


router = APIRouter(tags=["temporary-repositories"])


def _serialize_repo(indexed) -> TemporaryRepoResponse:
    return TemporaryRepoResponse(
        repo_id=indexed.repo_id,
        repo_name=indexed.repo_name,
        source_type=indexed.source_type,
        is_persistent=indexed.is_persistent,
        local_path=indexed.local_path,
        collection_name=indexed.collection_name,
        file_count=indexed.file_count,
        doc_count=indexed.doc_count,
        ignored_file_count=indexed.ignored_file_count,
        chunk_count=indexed.chunk_count,
    )


@router.post("/temporary-repos/github", response_model=TemporaryRepoResponse)
def post_github_temporary_repo(request: TemporaryGithubRepoRequest) -> TemporaryRepoResponse:
    """Clone and index a temporary public GitHub repository."""
    indexed = index_github_repo(
        github_url=request.github_url,
        session_id=request.session_id,
        branch=request.branch,
        retrieval_mode=request.retrieval_mode,
        use_llm=request.use_llm,
        use_llm_router=request.use_llm_router,
    )

    return _serialize_repo(indexed)


@router.post("/temporary-repos/zip", response_model=TemporaryRepoResponse)
async def post_zip_temporary_repo(
    session_id: str = Form(...),
    retrieval_mode: str = Form("fast"),
    use_llm: bool = Form(True),
    use_llm_router: bool = Form(True),
    file: UploadFile = File(...),
) -> TemporaryRepoResponse:
    """Index a temporary uploaded ZIP repository."""
    zip_bytes = await file.read()
    indexed = index_zip_repo(
        filename=file.filename or "uploaded_repo.zip",
        zip_bytes=zip_bytes,
        session_id=session_id,
        retrieval_mode=retrieval_mode,
        use_llm=use_llm,
        use_llm_router=use_llm_router,
    )

    return _serialize_repo(indexed)


@router.delete("/temporary-repos/{repo_id}", response_model=TemporaryRepoCleanupResponse)
def delete_temporary_repo(repo_id: str, session_id: str | None = None) -> TemporaryRepoCleanupResponse:
    """Clean up one temporary repository and clear matching session state."""
    deleted = cleanup_temporary_repo(
        repo_id=repo_id,
        session_id=session_id,
    )

    return TemporaryRepoCleanupResponse(
        repo_id=repo_id,
        deleted=deleted,
    )
