import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from src.settings import QDRANT_COLLECTION


def main() -> None:
    load_dotenv(override=True)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY") or None

    repo_id = input("Repo ID to inspect: ").strip()

    if not repo_id:
        raise ValueError("Repo ID is required")

    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )

    result = client.count(
        collection_name=QDRANT_COLLECTION,
        count_filter=Filter(
            must=[
                FieldCondition(
                    key="repo_id",
                    match=MatchValue(value=repo_id),
                )
            ]
        ),
        exact=True,
    )

    print("=" * 100)
    print("Qdrant records")
    print("=" * 100)
    print(f"Collection: {QDRANT_COLLECTION}")
    print(f"Repo ID: {repo_id}")
    print(f"Point count: {result.count}")


if __name__ == "__main__":
    main()