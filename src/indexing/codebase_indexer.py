"""Repository indexing workflow.

This module owns scan, parse, chunk, graph-build, vector indexing, and metadata
writeback for new or refreshed repository indexes.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.agent_core.agent import CodebaseAgent
from src.agent_core.query_router import LLMQueryRouter
from src.agent_core.tools import CodebaseTools
from src.chunking.code_chunker import build_code_chunks
from src.chunking.markdown_chunker import build_markdown_chunks, scan_markdown_files
from src.ingestion.scanner import scan_json_files, scan_text_files
from src.parsing.json_parser import parse_json_file
from src.parsing.text_parser import parse_text_file
from src.chunking.text_chunker import build_text_chunks
from src.core.constants import (
    DOC_EXTENSIONS,
    IGNORE_DIRS,
    INDEX_STATUS_INDEXED,
    JSON_EXTENSIONS,
    PYTHON_EXTENSIONS,
    REPO_SOURCE_COMPANY,
    REPO_SOURCE_CUSTOM_LOCAL,
    REPO_VISIBILITY_COMPANY,
    REPO_VISIBILITY_PRIVATE_SESSION,
    TEXT_EXTENSIONS,
)
from src.generation.answer_generator import GroundedAnswerGenerator
from src.generation.llm import GeminiLLM
from src.graph.code_graph import build_code_graph
from src.indexing.models import IndexedCodebase
from src.parsing.ast_parser import parse_python_file
from src.retrieval.retriever import CodeRetriever
from src.ingestion.scanner import scan_python_files
from src.core.settings import RETRIEVAL_MODE_FAST
from src.storage.metadata_store import MetadataStore
from src.storage.qdrant_vector_store import QdrantCodeVectorStore


def make_collection_name(repo_path: str | Path) -> str:
    """Create a stable, safe collection name from a repository folder name."""
    repo_path = Path(repo_path).resolve()
    name = repo_path.name.lower().replace(" ", "_").replace("-", "_")

    if len(name) < 3:
        name = f"repo_{name}"

    return name


def count_ignored_files(repo_path: str | Path) -> int:
    """Count files that are not currently indexed by the application."""
    repo_path = Path(repo_path).resolve()
    ignored_count = 0

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue

        parts = set(path.parts)
        if any(ignored_dir in parts for ignored_dir in IGNORE_DIRS):
            continue

        suffix = path.suffix.lower()
        name_lower = path.name.lower()
        parts_lower = {part.lower() for part in path.parts}

        is_python = suffix in PYTHON_EXTENSIONS
        is_readme = name_lower.startswith("readme") and suffix in DOC_EXTENSIONS
        is_docs_markdown = "docs" in parts_lower and suffix in DOC_EXTENSIONS
        is_json = suffix in JSON_EXTENSIONS
        is_text = suffix in TEXT_EXTENSIONS

        if not (is_python or is_readme or is_docs_markdown or is_json or is_text):
            ignored_count += 1

    return ignored_count


def build_optional_llm(enabled: bool) -> GeminiLLM | None:
    """Build an optional Gemini client with graceful fallback to None."""
    if not enabled:
        return None

    try:
        return GeminiLLM()
    except Exception:
        return None


def build_codebase_agent(
    repo_path: str | Path,
    collection_name: str | None = None,
    reset_collection: bool = True,
    use_llm: bool = True,
    retrieval_mode: str = RETRIEVAL_MODE_FAST,
    use_llm_router: bool = True,
    repo_id: str | None = None,
    repo_name: str | None = None,
    source_type: str = REPO_SOURCE_CUSTOM_LOCAL,
    is_persistent: bool | None = None,
    local_path: str | None = None,
    github_url: str | None = None,
    branch: str | None = None,
    commit_hash: str | None = None,
    expires_at: datetime | None = None,
    save_metadata: bool = True,
) -> IndexedCodebase:
    """Scan, parse, chunk, embed, index, and wire a ready-to-use codebase agent."""
    repo_path = Path(repo_path).resolve()

    if collection_name is None:
        collection_name = make_collection_name(repo_path)

    if repo_id is None:
        repo_id = collection_name

    if repo_name is None:
        repo_name = repo_path.name

    if is_persistent is None:
        is_persistent = source_type == REPO_SOURCE_COMPANY

    if source_type == REPO_SOURCE_COMPANY:
        visibility = REPO_VISIBILITY_COMPANY
    else:
        visibility = REPO_VISIBILITY_PRIVATE_SESSION

    if local_path is None:
        local_path = str(repo_path)

    if not is_persistent and expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repo path is not a directory: {repo_path}")

    python_files = scan_python_files(repo_path)
    markdown_files = scan_markdown_files(repo_path)
    json_files = scan_json_files(repo_path)
    text_files = scan_text_files(repo_path)
    ignored_file_count = count_ignored_files(repo_path)
    all_chunks = []

    for file_path in python_files:
        parsed_file = parse_python_file(file_path)
        chunks = build_code_chunks(parsed_file, repo_root=repo_path)
        all_chunks.extend(chunks)

    for file_path in markdown_files:
        chunks = build_markdown_chunks(file_path, repo_root=repo_path)
        all_chunks.extend(chunks)

    for file_path in json_files:
        parsed_json = parse_json_file(file_path, repo_root=repo_path)
        chunks = build_text_chunks(parsed_json)
        all_chunks.extend(chunks)

    for file_path in text_files:
        parsed_text = parse_text_file(file_path, repo_root=repo_path)
        chunks = build_text_chunks(parsed_text)
        all_chunks.extend(chunks)

    code_graph = build_code_graph(repo_path)
    vector_store = QdrantCodeVectorStore(repo_id=repo_id)

    if reset_collection:
        vector_store.reset_collection()

    vector_store.add_chunks(all_chunks)

    if save_metadata:
        metadata_store = MetadataStore()
        indexed_at = datetime.now(timezone.utc)

        metadata_store.upsert_repository(
            repo_id=repo_id,
            name=repo_name,
            source_type=source_type,
            visibility=visibility,
            is_persistent=is_persistent,
            collection_name=collection_name,
            status=INDEX_STATUS_INDEXED,
            file_count=len(python_files),
            doc_count=len(markdown_files),
            ignored_file_count=ignored_file_count,
            chunk_count=len(all_chunks),
            local_path=local_path,
            github_url=github_url,
            branch=branch,
            commit_hash=commit_hash,
            indexed_at=indexed_at,
            expires_at=expires_at,
        )

        metadata_store.replace_chunks(
            repo_id=repo_id,
            chunks=all_chunks,
        )

        metadata_store.replace_code_graph(
            repo_id=repo_id,
            code_graph=code_graph,
        )

        code_graph = metadata_store.load_code_graph(repo_id)

    retriever = CodeRetriever(
        vector_store=vector_store,
        indexed_chunks=all_chunks,
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
        repo_id=repo_id,
        repo_name=repo_name,
        source_type=source_type,
        is_persistent=is_persistent,
        repo_path=repo_path,
        collection_name=collection_name,
        file_count=len(python_files),
        doc_count=len(markdown_files),
        ignored_file_count=ignored_file_count,
        chunk_count=len(all_chunks),
        code_graph=code_graph,
        vector_store=vector_store,
        retriever=retriever,
        tools=tools,
        agent=agent,
        json_count=len(json_files),
        text_count=len(text_files),
    )
