"""Shared indexing models used by build and load workflows."""

from dataclasses import dataclass
from pathlib import Path

from src.agent_core.agent import CodebaseAgent
from src.agent_core.tools import CodebaseTools
from src.graph.code_graph import CodeGraph
from src.retrieval.retriever import CodeRetriever
from src.storage.qdrant_vector_store import QdrantCodeVectorStore


@dataclass
class IndexedCodebase:
    """Runtime bundle for a loaded or newly indexed repository."""

    repo_id: str
    repo_name: str
    source_type: str
    is_persistent: bool
    repo_path: Path
    collection_name: str
    file_count: int
    doc_count: int
    ignored_file_count: int
    chunk_count: int
    code_graph: CodeGraph
    vector_store: QdrantCodeVectorStore
    retriever: CodeRetriever
    tools: CodebaseTools
    agent: CodebaseAgent

    @property
    def local_path(self) -> str:
        """Return the repository path as a string for UI/API serialization."""
        return str(self.repo_path)
