"""
Core indexer — orchestrates the parse → chunk → embed → store pipeline.

This module is file-type agnostic: it dispatches to the appropriate
parser and chunker based on ``FileType``.
"""

from pathlib import Path
from typing import List, Optional

from src.schemas import (
    Chunk, ChunkType, FileType, ParsedDocument, SourceType,
)
from src.parsing.ast_parser import parse_python_file
from src.parsing.markdown_parser import parse_markdown_file
from src.parsing.text_parser import parse_text_file
from src.parsing.json_parser import parse_json_file
from src.parsing.yaml_parser import parse_yaml_file
from src.chunking.code_chunker import chunk_code
from src.chunking.text_chunker import chunk_text
from src.chunking.markdown_chunker import chunk_markdown
from src.metadata.metadata_builder import build_chunk_metadata
from src.metadata.id_generator import generate_chunk_id
from src.ingestion.file_type_detector import detect_file_type
from src.storage.vector_store import VectorStore
from src.storage.keyword_store import KeywordStore
from src.storage.metadata_store import MetadataStore
from src.storage.file_store import FileStore


# ── Parser dispatch ──────────────────────────────────────────────────

_PARSER_MAP = {
    FileType.PYTHON: parse_python_file,
    FileType.MARKDOWN: parse_markdown_file,
    FileType.TEXT: parse_text_file,
    FileType.JSON: parse_json_file,
    FileType.YAML: parse_yaml_file,
}

_CHUNK_TYPE_MAP = {
    FileType.PYTHON: ChunkType.CODE,
    FileType.MARKDOWN: ChunkType.MARKDOWN,
    FileType.TEXT: ChunkType.TEXT,
    FileType.JSON: ChunkType.TEXT,
    FileType.YAML: ChunkType.TEXT,
}

_LANGUAGE_MAP = {
    FileType.PYTHON: "python",
    FileType.MARKDOWN: "markdown",
    FileType.TEXT: "text",
    FileType.JSON: "json",
    FileType.YAML: "yaml",
}


class Indexer:
    """
    Orchestrates the full indexing pipeline for a single file.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        keyword_store: KeywordStore,
        metadata_store: MetadataStore,
        file_store: FileStore,
    ):
        self.vector_store = vector_store
        self.keyword_store = keyword_store
        self.metadata_store = metadata_store
        self.file_store = file_store

    def index_file(
        self,
        file_path: str | Path,
        repo_root: Optional[str | Path] = None,
        source: SourceType = SourceType.REPO,
    ) -> List[Chunk]:
        """
        Parse, chunk, and index a single file.

        Returns the list of ``Chunk`` objects created.
        """
        file_path = Path(file_path).resolve()
        file_type = detect_file_type(file_path)

        if file_type == FileType.UNKNOWN:
            return []

        # Compute relative path
        if repo_root:
            try:
                relative_path = str(file_path.relative_to(Path(repo_root).resolve()))
            except ValueError:
                relative_path = str(file_path)
        else:
            relative_path = str(file_path)

        # 1. Parse
        parser = _PARSER_MAP.get(file_type)
        if parser is None:
            return []

        doc: ParsedDocument = parser(file_path, relative_path=relative_path)
        doc.source = source

        # 2. Store raw file content
        self.file_store.put(relative_path, doc.source_code)

        # 3. Chunk
        chunk_type = _CHUNK_TYPE_MAP.get(file_type, ChunkType.TEXT)

        if file_type == FileType.PYTHON:
            chunk_results = chunk_code(doc)
        elif file_type == FileType.MARKDOWN:
            chunk_results = chunk_markdown(doc)
        else:
            chunk_results = chunk_text(doc)

        if not chunk_results:
            return []

        # 4. Build Chunk objects with metadata
        language = _LANGUAGE_MAP.get(file_type, "text")
        chunks: List[Chunk] = []

        for i, cr in enumerate(chunk_results):
            metadata = build_chunk_metadata(
                chunk_result=cr,
                file_path=str(file_path),
                relative_path=relative_path,
                chunk_type=chunk_type,
                source=source,
                language=language,
                chunk_index=i,
            )

            chunk = Chunk(
                chunk_id=metadata["chunk_id"],
                text=cr.text,
                content=cr.content,
                chunk_type=chunk_type,
                metadata=metadata,
            )
            chunks.append(chunk)

        # 5. Add to all stores
        self.vector_store.add_chunks(chunks)
        self.keyword_store.add_chunks(chunks)

        for chunk in chunks:
            self.metadata_store.add(chunk.chunk_id, chunk.metadata)

        return chunks
