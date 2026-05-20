from sqlalchemy import text

from src.core.settings import EMBEDDING_DIMENSION
from src.db.models import Base
from src.db.session import engine


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id varchar(255) PRIMARY KEY,
                    repo_id varchar(255) NOT NULL,
                    point_id uuid NOT NULL,
                    text text NOT NULL,
                    source_type varchar(50),
                    relative_path text NOT NULL,
                    start_line integer,
                    end_line integer,
                    symbol_name varchar(255),
                    qualified_name varchar(500),
                    symbol_type varchar(100),
                    heading text,
                    embedding vector({EMBEDDING_DIMENSION}) NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo_id "
                "ON chunk_embeddings (repo_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo_path "
                "ON chunk_embeddings (repo_id, relative_path)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo_symbol "
                "ON chunk_embeddings (repo_id, qualified_name)"
            )
        )

    Base.metadata.create_all(bind=engine)
    print("Supabase/Postgres tables created successfully.")


if __name__ == "__main__":
    main()
