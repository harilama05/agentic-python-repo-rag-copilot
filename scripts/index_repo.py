"""
Index a repository from the command line.

Usage:
    python -m scripts.index_repo --repo data/repos/sample_python_repo
"""

import argparse
from src.indexing.repo_indexer import index_repository


def main():
    parser = argparse.ArgumentParser(description="Index a Python repository")
    parser.add_argument("--repo", required=True, help="Path to the repository")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--no-reset", action="store_true", help="Don't reset index")
    parser.add_argument("--no-reranker", action="store_true", help="Disable reranker")
    args = parser.parse_args()

    print(f"Indexing: {args.repo}")

    indexed = index_repository(
        repo_path=args.repo,
        collection_name=args.collection,
        reset=not args.no_reset,
        use_reranker=not args.no_reranker,
    )

    print(f"✅ Done!")
    print(f"   Files: {indexed.file_count}")
    print(f"   Chunks: {indexed.chunk_count}")
    print(f"   Collection: {indexed.collection_name}")

    # Quick test
    print("\n--- Quick Test ---")
    questions = [
        "What functions are defined in this codebase?",
    ]

    for q in questions:
        response = indexed.agent.invoke(q)
        print(f"\nQ: {q}")
        print(f"A: {response.answer[:200]}...")


if __name__ == "__main__":
    main()