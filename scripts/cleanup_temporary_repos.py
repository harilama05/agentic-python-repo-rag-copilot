import argparse

from src.storage.repository_lifecycle import (
    cleanup_expired_temporary_repositories,
    list_expired_temporary_repositories,
)


def print_expired_repos() -> None:
    expired_repos = list_expired_temporary_repositories()

    print("=" * 100)
    print("Expired temporary repositories")
    print("=" * 100)

    if not expired_repos:
        print("No expired temporary repositories found.")
        return

    for repo in expired_repos:
        print(f"Repo ID:     {repo.repo_id}")
        print(f"Repo name:   {repo.repo_name}")
        print(f"Source type: {repo.source_type}")
        print(f"Local path:  {repo.local_path}")
        print(f"Expires at:  {repo.expires_at}")
        print("-" * 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Clean up expired temporary repositories from PostgreSQL, "
            "pgvector embeddings, and runtime folders."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show repos that would be deleted without deleting them.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List expired temporary repositories.",
    )

    args = parser.parse_args()

    if args.list:
        print_expired_repos()
        return

    if args.dry_run:
        print_expired_repos()
        print()
        print("Dry run only. Nothing was deleted.")
        return

    deleted_repo_ids = cleanup_expired_temporary_repositories(dry_run=False)

    print("=" * 100)
    print("Temporary repository cleanup complete")
    print("=" * 100)

    if not deleted_repo_ids:
        print("No expired temporary repositories were deleted.")
        return

    print("Deleted repositories:")

    for repo_id in deleted_repo_ids:
        print(f"- {repo_id}")


if __name__ == "__main__":
    main()
