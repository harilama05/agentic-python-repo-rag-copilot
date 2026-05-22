from src.ingestion.zip_ingestion import ingest_zip_path


def main() -> None:
    zip_path = input("ZIP path: ").strip()

    repo = ingest_zip_path(zip_path)

    print("=" * 100)
    print("ZIP repo ingested")
    print("=" * 100)
    print(f"Repo ID:           {repo.repo_id}")
    print(f"Name:              {repo.name}")
    print(f"Original filename: {repo.original_filename}")
    print(f"Local path:        {repo.local_path}")


if __name__ == "__main__":
    main()