import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text


def test_postgres() -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is not set")

    engine = create_engine(database_url)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 AS ok"))
        row = result.fetchone()

    print(f"PostgreSQL connection OK: {row.ok}")


def test_qdrant() -> None:
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY") or None

    if not qdrant_url:
        raise ValueError("QDRANT_URL is not set")

    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )

    collections = client.get_collections()

    print("Qdrant connection OK")
    print(f"Collections: {collections.collections}")


def main() -> None:
    load_dotenv(override=True)

    test_postgres()
    test_qdrant()


if __name__ == "__main__":
    main()