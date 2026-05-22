"""Manual smoke test for loading an already indexed repository."""

import sys

from src.indexing.codebase_loader import load_existing_codebase_agent
from src.core.settings import RETRIEVAL_MODE_FAST


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    """Load one existing repository and ask a documentation-style question."""
    repo_id = input("Repo ID to load: ").strip()

    indexed = load_existing_codebase_agent(
        repo_id=repo_id,
        retrieval_mode=RETRIEVAL_MODE_FAST,
        use_llm=False,
        use_llm_router=True,
    )

    print("=" * 100)
    print("Loaded existing repository")
    print("=" * 100)
    print(f"Repo ID: {indexed.repo_id}")
    print(f"Repo name: {indexed.repo_name}")
    print(f"Source type: {indexed.source_type}")
    print(f"Persistent: {indexed.is_persistent}")
    print(f"Repo path: {indexed.repo_path}")
    print(f"Collection: {indexed.collection_name}")

    question = "Dự án này dùng để làm gì?"
    response = indexed.agent.answer(question)

    print("=" * 100)
    print(f"Question: {question}")
    print("=" * 100)
    print(response.answer)
    print("=" * 100)
    print("Sources:")
    for source in response.sources:
        print(source)


if __name__ == "__main__":
    main()
