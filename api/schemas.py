"""Shared API request and response schemas.

These Pydantic models define the stable contract between the FastAPI backend
and any frontend client.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Simple health-check response."""

    status: str = "ok"


class APIErrorResponse(BaseModel):
    """Standard error response returned by API exception handlers."""

    error: str
    detail: str


class CompanyRepoSummary(BaseModel):
    """Indexed company repository summary returned by the API."""

    repo_id: str
    repo_name: str
    source_type: Optional[str] = None
    is_persistent: bool
    local_path: Optional[str] = None
    collection_name: Optional[str] = None
    file_count: int = 0
    doc_count: int = 0
    ignored_file_count: int = 0
    chunk_count: int = 0


class LoadCompanyRepoRequest(BaseModel):
    """Request payload for loading an indexed company repository.

    session_id is optional. If omitted, the API creates a new session_id and
    returns it in the response.
    """

    session_id: Optional[str] = None
    retrieval_mode: str = "fast"
    use_llm: bool = True
    use_llm_router: bool = True


class TemporaryGithubRepoRequest(BaseModel):
    """Request payload for indexing a temporary GitHub repository."""

    session_id: Optional[str] = None
    github_url: str = Field(min_length=1)
    branch: Optional[str] = None
    retrieval_mode: str = "fast"
    use_llm: bool = True
    use_llm_router: bool = True


class RepositorySessionResponse(BaseModel):
    """Response payload describing a loaded or indexed repository session."""

    session_id: str
    repo_id: str
    repo_name: str
    source_type: str
    is_persistent: bool
    local_path: str
    collection_name: str
    file_count: int
    doc_count: int
    text_count: int = 0
    docs_text_count: int = 0
    json_count: int = 0
    ignored_file_count: int
    chunk_count: int
    retrieval_mode: str


# Backward-compatible alias for existing imports.
TemporaryRepoResponse = RepositorySessionResponse


class ChatRequest(BaseModel):
    """Request payload for answering a repository question."""

    session_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ChatResponse(BaseModel):
    """Serialized agent response returned by the API."""

    session_id: str
    question: str
    query_type: str
    answer: str
    tools_used: List[str]
    sources: List[Dict[str, Any]]
    raw_results: Dict[str, Any]


class TemporaryRepoCleanupResponse(BaseModel):
    """Response returned after temporary repo cleanup."""

    repo_id: str
    session_id: Optional[str] = None
    deleted: bool
