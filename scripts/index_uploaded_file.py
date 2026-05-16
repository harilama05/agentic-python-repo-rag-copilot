"""
Index a single uploaded file from the command line.

Usage:
    python -m scripts.index_uploaded_file --file path/to/file.py
"""

import argparse
from src.indexing.upload_indexer import index_uploaded_file
from src.indexing.indexer import Indexer
from src.storage.vector_store import VectorStore
from src.storage.keyword_store import KeywordStore
from src.storage.metadata_store import MetadataStore
from src.storage.file_store import FileStore
from src.config import settings


def main():
    parser = argparse.ArgumentParser(description="Index a single file")
    parser.add_argument("--file", required=True, help="Path to the file")
    args = parser.parse_args()

    settings.ensure_dirs()

    indexer = Indexer(
        vector_store=VectorStore(),
        keyword_store=KeywordStore(),
        metadata_store=MetadataStore(),
        file_store=FileStore(),
    )

    chunks = index_uploaded_file(indexer, args.file)
    print(f"✅ Indexed {len(chunks)} chunks from {args.file}")


if __name__ == "__main__":
    main()
