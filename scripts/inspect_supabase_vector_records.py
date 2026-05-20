from dotenv import load_dotenv
from sqlalchemy import text

from src.db.session import get_db_session


def main() -> None:
    load_dotenv(override=True)

    repo_id = input("Repo ID to inspect: ").strip()

    if not repo_id:
        raise ValueError("Repo ID is required")

    with get_db_session() as session:
        result = session.execute(
            text(
                """
                SELECT count(*) AS point_count
                FROM chunk_embeddings
                WHERE repo_id = :repo_id
                """
            ),
            {"repo_id": repo_id},
        )
        row = result.fetchone()

    print("=" * 100)
    print("Supabase vector records")
    print("=" * 100)
    print(f"Repo ID: {repo_id}")
    print(f"Embedding count: {row.point_count}")


if __name__ == "__main__":
    main()
