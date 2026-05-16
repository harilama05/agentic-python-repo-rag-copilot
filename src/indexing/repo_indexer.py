"""
Repository indexer — scans and indexes an entire Python repository.

This is the main entry point for indexing a local repo.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.config import settings
from src.schemas import SourceType
from src.ingestion.scanner import scan_repository
from src.ingestion.document_registry import DocumentRegistry
from src.indexing.indexer import Indexer
from src.indexing.incremental_indexer import IncrementalIndexer
from src.storage.vector_store import VectorStore
from src.storage.keyword_store import KeywordStore
from src.storage.metadata_store import MetadataStore
from src.storage.file_store import FileStore
from src.retrieval.retriever import Retriever
from src.reranking.reranker import Reranker
from src.generation.answer_generator import AnswerGenerator
from src.agent.tools import AgentTools
from src.agent.graph import AgentGraph, create_agent_graph


@dataclass
class IndexedCodebase:
    """Result of indexing a repository — contains everything needed to query it."""
    repo_path: Path
    collection_name: str
    file_count: int
    chunk_count: int
    vector_store: VectorStore
    keyword_store: KeywordStore
    metadata_store: MetadataStore
    file_store: FileStore
    retriever: Retriever
    agent: AgentGraph


def index_repository(
    repo_path: str | Path,
    collection_name: Optional[str] = None,
    reset: bool = True,
    incremental: bool = False,
    use_reranker: bool = True,
    use_llm: bool = True,
) -> IndexedCodebase:
    """
    Scan, parse, chunk, embed, and index a Python repository.

    Returns an ``IndexedCodebase`` with a ready-to-use ``AgentGraph``.
    """
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")

    # Ensure data directories exist
    settings.ensure_dirs()

    # Collection name from repo folder
    if collection_name is None:
        name = repo_path.name.lower().replace(" ", "_").replace("-", "_")
        collection_name = name if len(name) >= 3 else f"repo_{name}"

    # Initialize stores
    vector_store = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=collection_name,
    )
    keyword_store = KeywordStore(persist_dir=settings.bm25_persist_dir)
    metadata_store = MetadataStore(persist_dir=settings.metadata_persist_dir)
    file_store = FileStore(persist_dir=settings.metadata_persist_dir)

    if reset:
        vector_store.reset()
        keyword_store.reset()
        metadata_store.clear()
        file_store.clear()

    # Build indexer
    indexer = Indexer(
        vector_store=vector_store,
        keyword_store=keyword_store,
        metadata_store=metadata_store,
        file_store=file_store,
    )

    # Scan
    files = scan_repository(repo_path)

    # Index
    total_chunks = 0

    if incremental:
        registry = DocumentRegistry()
        inc_indexer = IncrementalIndexer(indexer, registry)

        for file_path in files:
            chunks = inc_indexer.index_file(
                file_path=file_path,
                repo_root=repo_path,
                source=SourceType.REPO,
            )
            total_chunks += len(chunks)

        registry.save()
    else:
        for file_path in files:
            chunks = indexer.index_file(
                file_path=file_path,
                repo_root=repo_path,
                source=SourceType.REPO,
            )
            total_chunks += len(chunks)

    # Persist stores
    keyword_store.save()
    metadata_store.save()
    file_store.save()

    # Build retriever and agent
    retriever = Retriever(
        vector_store=vector_store,
        keyword_store=keyword_store,
        metadata_store=metadata_store,
    )

    reranker = None
    if use_reranker:
        try:
            reranker = Reranker()
        except Exception:
            reranker = None

    generator = None
    if use_llm and settings.openai_api_key:
        try:
            generator = AnswerGenerator()
        except Exception:
            generator = None

    tools = AgentTools(
        retriever=retriever,
        file_store=file_store,
        repo_root=repo_path,
    )

    agent = create_agent_graph(
        tools=tools,
        retriever=retriever,
        reranker=reranker,
        generator=generator,
    )

    return IndexedCodebase(
        repo_path=repo_path,
        collection_name=collection_name,
        file_count=len(files),
        chunk_count=total_chunks,
        vector_store=vector_store,
        keyword_store=keyword_store,
        metadata_store=metadata_store,
        file_store=file_store,
        retriever=retriever,
        agent=agent,
    )
