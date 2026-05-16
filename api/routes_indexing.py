"""
Indexing API routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/index", tags=["indexing"])

# Global state for the indexed codebase
_indexed_codebase = None


class IndexRequest(BaseModel):
    repo_path: str
    collection_name: Optional[str] = None
    reset: bool = True
    use_reranker: bool = True


class IndexResponse(BaseModel):
    status: str
    file_count: int
    chunk_count: int
    collection_name: str


@router.post("/repository", response_model=IndexResponse)
async def index_repository(request: IndexRequest):
    """Index a local Python repository."""
    global _indexed_codebase

    try:
        from src.indexing.repo_indexer import index_repository as _index_repo

        indexed = _index_repo(
            repo_path=request.repo_path,
            collection_name=request.collection_name,
            reset=request.reset,
            use_reranker=request.use_reranker,
        )
        _indexed_codebase = indexed

        return IndexResponse(
            status="success",
            file_count=indexed.file_count,
            chunk_count=indexed.chunk_count,
            collection_name=indexed.collection_name,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def get_indexed_codebase():
    return _indexed_codebase
