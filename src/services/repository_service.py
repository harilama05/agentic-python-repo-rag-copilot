"""Repository-oriented service functions for UI and API layers.

These functions centralize repository loading, temporary repo ingestion, and
cleanup so entrypoints stay thin and behavior remains consistent.
"""

from typing import Optional

from src.core.constants import REPO_SOURCE_GITHUB, REPO_SOURCE_ZIP_UPLOAD
from src.indexing.codebase_indexer import build_codebase_agent
from src.indexing.codebase_loader import load_existing_codebase_agent
from src.indexing.models import IndexedCodebase
from src.ingestion.github_ingestion import clone_github_repo
from src.ingestion.zip_ingestion import ingest_zip_bytes
from src.services.session_store import SessionStore, get_default_session_store
from src.core.settings import RETRIEVAL_MODE_FAST
from src.storage.repository_lifecycle import (
    cleanup_temporary_repository,
    list_persistent_repositories,
)


def _resolve_session_store(session_store: SessionStore | None) -> SessionStore:
    return session_store or get_default_session_store()


def _cleanup_previous_temporary_repo(
    *,
    session_id: str | None,
    session_store: SessionStore,
) -> None:
    if not session_id:
        return

    active_temp_repo_id = session_store.get_active_temp_repo_id(session_id)

    if not active_temp_repo_id:
        return

    deleted = cleanup_temporary_repository(active_temp_repo_id)

    if deleted:
        session_store.set_active_temp_repo_id(session_id, None)


def _store_indexed_codebase(
    *,
    session_id: str | None,
    session_store: SessionStore,
    indexed: IndexedCodebase,
) -> IndexedCodebase:
    if not session_id:
        return indexed

    session_store.set_indexed_codebase(session_id, indexed)
    session_store.clear_chat_history(session_id)

    if indexed.source_type in {REPO_SOURCE_GITHUB, REPO_SOURCE_ZIP_UPLOAD}:
        session_store.set_active_temp_repo_id(session_id, indexed.repo_id)
    else:
        session_store.set_active_temp_repo_id(session_id, None)

    return indexed


def list_company_repos():
    """List persistent repositories available for loading."""
    return list_persistent_repositories()


def load_company_repo(
    repo_id: str,
    *,
    session_id: str | None = None,
    retrieval_mode: str = RETRIEVAL_MODE_FAST,
    use_llm: bool = True,
    use_llm_router: bool = True,
    session_store: SessionStore | None = None,
) -> IndexedCodebase:
    """Load an already indexed persistent repository and bind it to a session."""
    store = _resolve_session_store(session_store)
    _cleanup_previous_temporary_repo(session_id=session_id, session_store=store)

    indexed = load_existing_codebase_agent(
        repo_id=repo_id,
        retrieval_mode=retrieval_mode,
        use_llm=use_llm,
        use_llm_router=use_llm_router,
    )

    return _store_indexed_codebase(
        session_id=session_id,
        session_store=store,
        indexed=indexed,
    )


def index_github_repo(
    github_url: str,
    *,
    session_id: str | None = None,
    branch: str | None = None,
    retrieval_mode: str = RETRIEVAL_MODE_FAST,
    use_llm: bool = True,
    use_llm_router: bool = True,
    reset_collection: bool = True,
    session_store: SessionStore | None = None,
) -> IndexedCodebase:
    """Clone and index a temporary public GitHub repository."""
    store = _resolve_session_store(session_store)
    _cleanup_previous_temporary_repo(session_id=session_id, session_store=store)

    ingested_repo = clone_github_repo(
        github_url=github_url,
        branch=branch,
    )

    indexed = build_codebase_agent(
        repo_path=str(ingested_repo.local_path),
        collection_name=ingested_repo.repo_id,
        reset_collection=reset_collection,
        use_llm=use_llm,
        retrieval_mode=retrieval_mode,
        use_llm_router=use_llm_router,
        repo_id=ingested_repo.repo_id,
        repo_name=ingested_repo.name,
        source_type=REPO_SOURCE_GITHUB,
        is_persistent=False,
        local_path=str(ingested_repo.local_path),
        github_url=ingested_repo.github_url,
        branch=ingested_repo.branch,
        commit_hash=ingested_repo.commit_hash,
        save_metadata=True,
    )

    return _store_indexed_codebase(
        session_id=session_id,
        session_store=store,
        indexed=indexed,
    )


def index_zip_repo(
    *,
    filename: str,
    zip_bytes: bytes,
    session_id: str | None = None,
    retrieval_mode: str = RETRIEVAL_MODE_FAST,
    use_llm: bool = True,
    use_llm_router: bool = True,
    reset_collection: bool = True,
    session_store: SessionStore | None = None,
) -> IndexedCodebase:
    """Extract and index a temporary uploaded ZIP repository."""
    store = _resolve_session_store(session_store)
    _cleanup_previous_temporary_repo(session_id=session_id, session_store=store)

    ingested_repo = ingest_zip_bytes(
        filename=filename,
        zip_bytes=zip_bytes,
    )

    indexed = build_codebase_agent(
        repo_path=str(ingested_repo.local_path),
        collection_name=ingested_repo.repo_id,
        reset_collection=reset_collection,
        use_llm=use_llm,
        retrieval_mode=retrieval_mode,
        use_llm_router=use_llm_router,
        repo_id=ingested_repo.repo_id,
        repo_name=ingested_repo.name,
        source_type=REPO_SOURCE_ZIP_UPLOAD,
        is_persistent=False,
        local_path=str(ingested_repo.local_path),
        save_metadata=True,
    )

    return _store_indexed_codebase(
        session_id=session_id,
        session_store=store,
        indexed=indexed,
    )


def cleanup_temporary_repo(
    repo_id: str,
    *,
    session_id: str | None = None,
    session_store: SessionStore | None = None,
) -> bool:
    """Clean up a temporary repository and clear matching session state."""
    store = _resolve_session_store(session_store)
    deleted = cleanup_temporary_repository(repo_id)

    if session_id and store.get_active_temp_repo_id(session_id) == repo_id:
        store.set_active_temp_repo_id(session_id, None)
        session = store.get_or_create_session(session_id)

        if session.indexed_codebase is not None and session.indexed_codebase.repo_id == repo_id:
            session.indexed_codebase = None
            session.chat_history = []

    return deleted
