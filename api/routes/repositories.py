"""Routes for listing and loading already indexed company repositories."""

from uuid import uuid4

from fastapi import APIRouter

from api.schemas import (
    CompanyRepoSummary,
    LoadCompanyRepoRequest,
    RepositorySessionResponse,
)
from src.services.repository_service import list_company_repos, load_company_repo


router = APIRouter(tags=["repositories"])


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


@router.get("/company-repos", response_model=list[CompanyRepoSummary])
def get_company_repositories() -> list[CompanyRepoSummary]:
    """List already indexed company repositories."""
    repos = list_company_repos()

    return [
        CompanyRepoSummary(
            repo_id=repo.repo_id,
            repo_name=repo.repo_name,
            source_type=repo.source_type,
            is_persistent=repo.is_persistent,
            local_path=repo.local_path,
            collection_name=repo.collection_name,
            file_count=getattr(repo, "file_count", 0) or 0,
            doc_count=getattr(repo, "doc_count", 0) or 0,
            ignored_file_count=getattr(repo, "ignored_file_count", 0) or 0,
            chunk_count=repo.chunk_count,
        )
        for repo in repos
    ]


@router.post(
    "/company-repos/{repo_id}/load",
    response_model=RepositorySessionResponse,
)
def post_load_company_repo(
    repo_id: str,
    request: LoadCompanyRepoRequest,
) -> RepositorySessionResponse:
    """Load an indexed company repository into a session."""
    session_id = _ensure_session_id(request.session_id)

    indexed = load_company_repo(
        repo_id=repo_id,
        session_id=session_id,
        retrieval_mode=request.retrieval_mode,
        use_llm=request.use_llm,
        use_llm_router=request.use_llm_router,
    )

    return _serialize_repo(indexed, session_id=session_id)
