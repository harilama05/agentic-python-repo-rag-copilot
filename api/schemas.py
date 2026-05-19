"""Shared API request and response schemas.

These schemas keep route handlers thin and make the future FastAPI transport
layer explicit without changing the current business logic.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Simple health-check response."""

    status: str = "ok"


class CompanyRepoSummary(BaseModel):
    """Indexed company repository summary returned by the API."""

    repo_id: str
    repo_name: str
    source_type: Optional[str] = None
    is_persistent: bool
    local_path: Optional[str] = None
    collection_name: Optional[str] = None
    chunk_count: int


class LoadCompanyRepoRequest(BaseModel):
    """Request payload for loading an indexed company repository."""

    session_id: str
    retrieval_mode: str = "fast"
    use_llm: bool = True
    use_llm_router: bool = True


class TemporaryGithubRepoRequest(BaseModel):
    """Request payload for indexing a temporary GitHub repository."""

    session_id: str
    github_url: str
    branch: Optional[str] = None
    retrieval_mode: str = "fast"
    use_llm: bool = True
    use_llm_router: bool = True


class TemporaryRepoResponse(BaseModel):
    """Response payload describing a loaded or indexed repository."""

    repo_id: str
    repo_name: str
    source_type: str
    is_persistent: bool
    local_path: str
    collection_name: str
    file_count: int
    doc_count: int
    ignored_file_count: int
    chunk_count: int


class ChatRequest(BaseModel):
    """Request payload for answering a repository question."""

    session_id: str
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    """Serialized agent response returned by the API."""

    question: str
    query_type: str
    answer: str
    tools_used: List[str]
    sources: List[Dict[str, Any]]
    raw_results: Dict[str, Any]


class TemporaryRepoCleanupResponse(BaseModel):
    """Response returned after temporary repo cleanup."""

    repo_id: str
    deleted: bool
