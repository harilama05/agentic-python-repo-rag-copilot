import argparse
from dataclasses import dataclass
from pathlib import Path

from src.services.company_repos import get_company_repo, get_company_repo_options
from src.core.constants import REPO_SOURCE_COMPANY
from src.indexing.codebase_indexer import build_codebase_agent
from src.core.settings import RETRIEVAL_MODE_FAST
from src.storage.lifecycle import delete_repository


@dataclass
class ResolvedCompanyRepo:
    repo_id: str
    repo_name: str
    repo_path: Path


def list_company_repo_options() -> None:
    company_options = get_company_repo_options()

    print("=" * 100)
    print("Configured company repositories")
    print("=" * 100)

    for display_name, repo_id in company_options.items():
        repo = get_company_repo(repo_id)

        print(f"Name:        {display_name}")
        print(f"Repo ID:     {repo_id}")
        print(f"Path:        {repo.path}")
        print(f"Description: {repo.description}")
        print("-" * 100)


def resolve_company_repo(identifier: str) -> ResolvedCompanyRepo:
    """
    Resolve either:
    - display name, for example: TaskFlow API
    - repo_id, for example: taskflow_api
    """
    company_options = get_company_repo_options()

    if identifier in company_options:
        repo_name = identifier
        repo_id = company_options[identifier]
    else:
        matching_names = [
            display_name
            for display_name, option_repo_id in company_options.items()
            if option_repo_id == identifier
        ]

        if not matching_names:
            available = ", ".join(company_options.values())
            raise ValueError(
                f"Unknown company repo: {identifier}\n"
                f"Available repo IDs: {available}"
            )

        repo_name = matching_names[0]
        repo_id = identifier

    repo = get_company_repo(repo_id)

    return ResolvedCompanyRepo(
        repo_id=repo_id,
        repo_name=repo_name,
        repo_path=Path(repo.path),
    )


def index_company_repo(identifier: str) -> None:
    resolved = resolve_company_repo(identifier)

    repo_id = resolved.repo_id
    repo_name = resolved.repo_name
    repo_path = resolved.repo_path

    if not repo_path.exists():
        raise FileNotFoundError(f"Company repo path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Company repo path is not a directory: {repo_path}")

    print("=" * 100)
    print("Indexing company repository")
    print("=" * 100)
    print(f"Repo ID:   {repo_id}")
    print(f"Repo name: {repo_name}")
    print(f"Repo path: {repo_path}")
    print("=" * 100)

    print("Removing old indexed data for this repo if it exists...")
    deleted = delete_repository(
        repo_id=repo_id,
        delete_runtime_files=False,
        only_if_temporary=False,
    )

    if deleted:
        print("Old indexed data deleted.")
    else:
        print("No old indexed data found. This looks like a first-time index.")

    print("Building new index...")

    indexed = build_codebase_agent(
        repo_path=repo_path,
        collection_name=repo_id,
        reset_collection=True,
        use_llm=True,
        retrieval_mode=RETRIEVAL_MODE_FAST,
        use_llm_router=True,
        repo_id=repo_id,
        repo_name=repo_name,
        source_type=REPO_SOURCE_COMPANY,
        is_persistent=True,
        local_path=str(repo_path),
        save_metadata=True,
    )

    print("=" * 100)
    print("Company repository indexed successfully")
    print("=" * 100)
    print(f"Repo ID:                 {indexed.repo_id}")
    print(f"Repo name:               {indexed.repo_name}")
    print(f"Source type:             {indexed.source_type}")
    print(f"Persistent:              {indexed.is_persistent}")
    docs_text_count = indexed.doc_count + getattr(indexed, "text_count", 0)

    print(f"Python files indexed:    {indexed.file_count}")
    print(f"Docs/Text files indexed: {docs_text_count}")
    print(f"JSON files indexed:      {getattr(indexed, 'json_count', 0)}")
    print(f"Other files ignored:     {indexed.ignored_file_count}")
    print(f"Total chunks:            {indexed.chunk_count}")
    print(f"Collection:              {indexed.collection_name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Index or re-index a configured company repository into "
            "Supabase/Postgres metadata and pgvector embeddings."
        )
    )

    parser.add_argument(
        "repo",
        nargs="?",
        help="Company repo ID or display name, for example: taskflow_api",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured company repositories.",
    )

    args = parser.parse_args()

    if args.list:
        list_company_repo_options()
        return

    if not args.repo:
        list_company_repo_options()
        raise SystemExit(
            "Please provide a repo ID, for example:\n"
            "python -m scripts.index_company_repo taskflow_api"
        )

    index_company_repo(args.repo)


if __name__ == "__main__":
    main()
