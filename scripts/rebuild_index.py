"""Rebuild the entire index from scratch."""

import argparse
from src.indexing.repo_indexer import index_repository


def main():
    parser = argparse.ArgumentParser(description="Rebuild index")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    indexed = index_repository(repo_path=args.repo, reset=True)
    print(f"✅ Rebuilt: {indexed.chunk_count} chunks from {indexed.file_count} files")


if __name__ == "__main__":
    main()
