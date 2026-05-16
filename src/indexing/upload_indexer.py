"""
Upload indexer — indexes a single uploaded file into the existing stores.
"""

from pathlib import Path
from typing import List

from src.schemas import Chunk, SourceType
from src.indexing.indexer import Indexer


def index_uploaded_file(
    indexer: Indexer,
    file_path: str | Path,
) -> List[Chunk]:
    """
    Index a single uploaded file.

    Returns the list of chunks created.
    """
    return indexer.index_file(
        file_path=file_path,
        repo_root=None,
        source=SourceType.UPLOAD,
    )
