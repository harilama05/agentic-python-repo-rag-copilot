"""Repository loading workflow for already indexed repositories.

This module reconstructs runtime objects from Supabase/PostgreSQL metadata and
pgvector embeddings without re-scanning or re-indexing repository files.
"""

from pathlib import Path

from src.agent_core.agent import CodebaseAgent
from src.agent_core.query_router import LLMQueryRouter
from src.agent_core.tools import CodebaseTools
from src.core.constants import REPO_SOURCE_COMPANY
from src.generation.answer_generator import GroundedAnswerGenerator
from src.indexing.codebase_indexer import build_optional_llm
from src.indexing.models import IndexedCodebase
from src.retrieval.retriever import CodeRetriever
from src.storage.metadata import MetadataStore
from src.storage.supabase_vector_store import SupabaseCodeVectorStore
from src.storage.lifecycle import get_repository_snapshot


def _count_distinct_chunk_files_by_source_type(
    chunks: list[dict],
    source_type: str,
) -> int:
    """Count distinct files represented by chunks of a given source type."""
    paths: set[str] = set()

    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        chunk_source_type = chunk.get("source_type") or metadata.get("source_type")

        if chunk_source_type != source_type:
            continue

        relative_path = (
            chunk.get("relative_path")
            or metadata.get("relative_path")
            or metadata.get("file_path")
        )

        if relative_path:
            paths.add(str(relative_path).replace("\\", "/"))

    return len(paths)


def load_existing_codebase_agent(
    repo_id: str,
    retrieval_mode: str,
    use_llm: bool,
    use_llm_router: bool = True,
) -> IndexedCodebase:
    """Load an already indexed persistent repository from Supabase/PostgreSQL."""
    repo = get_repository_snapshot(repo_id)

    if repo is None:
        raise ValueError(f"Repository not found in database: {repo_id}")

    if not repo.is_persistent:
        raise ValueError(
            f"Repository {repo_id} is not persistent. "
            "Only persistent/company repositories can be loaded this way."
        )

    if not repo.local_path:
        raise ValueError(
            f"Repository {repo_id} does not have a local_path stored."
        )

    repo_path = Path(repo.local_path).resolve()

    collection_name = getattr(repo, "collection_name", None) or repo.repo_id
    repo_name = getattr(repo, "repo_name", None) or repo.repo_id
    source_type = getattr(repo, "source_type", None) or REPO_SOURCE_COMPANY
    metadata_store = MetadataStore()
    code_graph = metadata_store.load_code_graph(repo.repo_id)
    indexed_chunks = metadata_store.load_chunks(repo.repo_id)
    json_count = _count_distinct_chunk_files_by_source_type(indexed_chunks, "json")
    text_count = _count_distinct_chunk_files_by_source_type(indexed_chunks, "text")
    vector_store = SupabaseCodeVectorStore(repo_id=repo.repo_id)
    retriever = CodeRetriever(
        vector_store=vector_store,
        indexed_chunks=indexed_chunks,
    )
    tools = CodebaseTools(
        retriever=retriever,
        repo_root=repo_path,
        retrieval_mode=retrieval_mode,
        code_graph=code_graph,
    )

    shared_llm = build_optional_llm(use_llm or use_llm_router)
    router_llm = shared_llm if use_llm_router else None
    answer_llm = shared_llm if use_llm else None
    query_router = LLMQueryRouter(llm=router_llm)
    answer_generator = GroundedAnswerGenerator(answer_llm) if answer_llm is not None else None
    agent = CodebaseAgent(
        tools=tools,
        query_router=query_router,
        llm=answer_llm,
        use_llm=use_llm,
        answer_generator=answer_generator,
    )

    return IndexedCodebase(
        repo_id=repo.repo_id,
        repo_name=repo_name,
        source_type=source_type,
        is_persistent=repo.is_persistent,
        repo_path=repo_path,
        collection_name=collection_name,
        file_count=getattr(repo, "file_count", 0) or 0,
        doc_count=getattr(repo, "doc_count", 0) or 0,
        ignored_file_count=getattr(repo, "ignored_file_count", 0) or 0,
        chunk_count=getattr(repo, "chunk_count", 0) or 0,
        code_graph=code_graph,
        vector_store=vector_store,
        retriever=retriever,
        tools=tools,
        agent=agent,
        json_count=json_count,
        text_count=text_count,
    )
