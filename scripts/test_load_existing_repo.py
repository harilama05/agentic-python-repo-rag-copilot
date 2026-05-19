from src.indexer import load_existing_codebase_agent
from src.settings import RETRIEVAL_MODE_FAST


def main() -> None:
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