"""
Symbol search — finds chunks by exact or fuzzy symbol name match
using the metadata store (no embedding required).
"""

from typing import Any, Dict, List

from src.schemas import SearchResult
from src.storage.metadata_store import MetadataStore


class SymbolSearch:
    """
    Metadata-only symbol lookup — much faster than embedding search
    when the user asks about a specific function/class by name.
    """

    def __init__(self, metadata_store: MetadataStore):
        self._store = metadata_store

    def search(self, symbol_name: str) -> List[SearchResult]:
        """Find chunks whose symbol_name or qualified_name matches."""
        matches = self._store.find_by_symbol(symbol_name)

        results: List[SearchResult] = []
        for meta in matches:
            results.append(
                SearchResult(
                    chunk_id=meta.get("chunk_id", ""),
                    text="",  # text not stored in metadata store
                    metadata=meta,
                    score=1.0,  # exact match gets max score
                )
            )

        return results
