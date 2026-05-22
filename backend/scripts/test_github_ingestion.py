from src.ingestion.github_ingestion import clone_github_repo


def main() -> None:
    github_url = input("GitHub URL: ").strip()

    repo = clone_github_repo(github_url)

    print("=" * 100)
    print("GitHub repo cloned")
    print("=" * 100)
    print(f"Repo ID:      {repo.repo_id}")
    print(f"Name:         {repo.name}")
    print(f"GitHub URL:   {repo.github_url}")
    print(f"Branch:       {repo.branch}")
    print(f"Commit hash:  {repo.commit_hash}")
    print(f"Local path:   {repo.local_path}")


if __name__ == "__main__":
    main()