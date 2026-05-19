"""
Convenience entry points that ingest GitHub/ZIP inputs and index them.

API routes can call these functions directly instead of manually wiring
ingestion and indexing steps together.
"""

from pathlib import Path
from typing import Optional

from src.ingestion.github_ingestion import ingest_github_repo
from src.ingestion.zip_ingestion import (
    ingest_zip_bytes as prepare_zip_bytes,
    ingest_zip_path,
)
from src.indexing.repo_indexer import IndexedCodebase, index_prepared_repository
from src.schemas import SourceType


def index_github_repository(
    github_url: str,
    branch: str | None = None,
    collection_name: Optional[str] = None,
    force_refresh: bool = True,
    reset: bool = True,
    incremental: bool = False,
    use_reranker: bool = True,
    use_llm: bool = True,
) -> IndexedCodebase:
    """Clone, filter, and index a public GitHub repository."""
    prepared_repo = ingest_github_repo(
        github_url=github_url,
        branch=branch,
        force_refresh=force_refresh,
    )

    return index_prepared_repository(
        prepared_repo,
        collection_name=collection_name,
        reset=reset,
        incremental=incremental,
        use_reranker=use_reranker,
        use_llm=use_llm,
        source=SourceType.REPO,
    )


def index_zip_bytes(
    filename: str,
    zip_bytes: bytes,
    collection_name: Optional[str] = None,
    force_refresh: bool = True,
    reset: bool = True,
    incremental: bool = False,
    use_reranker: bool = True,
    use_llm: bool = True,
) -> IndexedCodebase:
    """Extract, filter, and index an uploaded ZIP archive."""
    prepared_repo = prepare_zip_bytes(
        filename=filename,
        zip_bytes=zip_bytes,
        force_refresh=force_refresh,
    )

    return index_prepared_repository(
        prepared_repo,
        collection_name=collection_name,
        reset=reset,
        incremental=incremental,
        use_reranker=use_reranker,
        use_llm=use_llm,
        source=SourceType.UPLOAD,
    )


def index_zip_file(
    zip_path: str | Path,
    collection_name: Optional[str] = None,
    force_refresh: bool = True,
    reset: bool = True,
    incremental: bool = False,
    use_reranker: bool = True,
    use_llm: bool = True,
) -> IndexedCodebase:
    """Extract, filter, and index a ZIP archive from disk."""
    prepared_repo = ingest_zip_path(
        zip_path=zip_path,
        force_refresh=force_refresh,
    )

    return index_prepared_repository(
        prepared_repo,
        collection_name=collection_name,
        reset=reset,
        incremental=incremental,
        use_reranker=use_reranker,
        use_llm=use_llm,
        source=SourceType.UPLOAD,
    )
