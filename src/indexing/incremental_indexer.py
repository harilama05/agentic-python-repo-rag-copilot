"""
Incremental indexer — only re-indexes files that have changed.

Uses the ``DocumentRegistry`` to track file hashes.
"""

from pathlib import Path
from typing import List

from src.schemas import Chunk, SourceType
from src.indexing.indexer import Indexer
from src.ingestion.document_registry import DocumentRegistry


class IncrementalIndexer:
    """
    Wraps ``Indexer`` and skips unchanged files.
    """

    def __init__(self, indexer: Indexer, registry: DocumentRegistry):
        self.indexer = indexer
        self.registry = registry

    def index_file(
        self,
        file_path: str | Path,
        repo_root: str | Path | None = None,
        source: SourceType = SourceType.REPO,
        force: bool = False,
    ) -> List[Chunk]:
        """
        Index a file only if it is new or has changed.

        Set ``force=True`` to re-index regardless.
        """
        file_path = Path(file_path).resolve()

        if not force and not self.registry.needs_reindex(file_path):
            return []

        chunks = self.indexer.index_file(
            file_path=file_path,
            repo_root=repo_root,
            source=source,
        )

        self.registry.mark_indexed(file_path, chunk_count=len(chunks))

        return chunks
