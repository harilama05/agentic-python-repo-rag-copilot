"""Routes for loading already indexed company repositories."""

from fastapi import APIRouter

from api.schemas import CompanyRepoSummary, LoadCompanyRepoRequest, TemporaryRepoResponse
from src.services.repository_service import list_company_repos, load_company_repo


router = APIRouter(tags=["repositories"])


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
            chunk_count=repo.chunk_count,
        )
        for repo in repos
    ]


@router.post("/company-repos/{repo_id}/load", response_model=TemporaryRepoResponse)
def post_load_company_repo(repo_id: str, request: LoadCompanyRepoRequest) -> TemporaryRepoResponse:
    """Load an indexed company repository into the caller's session."""
    indexed = load_company_repo(
        repo_id=repo_id,
        session_id=request.session_id,
        retrieval_mode=request.retrieval_mode,
        use_llm=request.use_llm,
        use_llm_router=request.use_llm_router,
    )

    return _serialize_repo(indexed)
