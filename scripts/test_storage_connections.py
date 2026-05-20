import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def describe_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    database = parsed.path.lstrip("/") or "unknown-database"

    if "supabase" in host:
        return f"Supabase PostgreSQL ({host}/{database})"

    return f"PostgreSQL ({host}/{database})"


def test_postgres() -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is not set")

    normalized_url = normalize_database_url(database_url)
    engine = create_engine(normalized_url)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 AS ok"))
        row = result.fetchone()
        vector_result = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_extension
                    WHERE extname = 'vector'
                ) AS vector_enabled
                """
            )
        )
        vector_row = vector_result.fetchone()

    print(f"{describe_database_url(normalized_url)} connection OK: {row.ok}")
    print(f"pgvector extension enabled: {bool(vector_row.vector_enabled)}")


def main() -> None:
    load_dotenv(override=True)

    test_postgres()


if __name__ == "__main__":
    main()
