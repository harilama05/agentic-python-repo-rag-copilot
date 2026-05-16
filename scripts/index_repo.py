from pathlib import Path

from src.indexer import build_codebase_agent


def main() -> None:
    repo_path = Path("examples/sample_python_repo")

    print("Indexing repo...")
    indexed = build_codebase_agent(
        repo_path=repo_path,
        collection_name="sample_python_repo",
        reset_collection=True,
    )

    print(f"Repo path: {indexed.repo_path}")
    print(f"Collection: {indexed.collection_name}")
    print(f"Found {indexed.file_count} Python files")
    print(f"Found {indexed.doc_count} documentation files")
    print(f"Ignored {indexed.ignored_file_count} other files")
    print(f"Built {indexed.chunk_count} total chunks")

    questions = [
        "Where is create_user implemented?",
        "Where is create_user used?",
        "What does UserService do?",
        "Find code related to user creation",
    ]

    print("\nAgent tests:")

    for question in questions:
        response = indexed.agent.answer(question)

        print("\n" + "=" * 100)
        print("Question:", response.question)
        print("Query type:", response.query_type)

        print("\nTools used:")
        for tool in response.tools_used:
            print("-", tool)

        print("\nAnswer:")
        print(response.answer)

        print("\nSources:")
        for source in response.sources:
            print("-", source)


if __name__ == "__main__":
    main()