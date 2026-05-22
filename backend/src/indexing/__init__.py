"""Canonical indexing package for repository indexing and loading."""

from src.indexing.codebase_indexer import build_codebase_agent, build_optional_llm, count_ignored_files, make_collection_name
from src.indexing.codebase_loader import load_existing_codebase_agent
from src.indexing.models import IndexedCodebase

__all__ = [
    "IndexedCodebase",
    "build_codebase_agent",
    "build_optional_llm",
    "count_ignored_files",
    "load_existing_codebase_agent",
    "make_collection_name",
]
