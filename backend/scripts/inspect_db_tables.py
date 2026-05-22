from sqlalchemy import inspect

from src.db.session import engine


def main() -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("=" * 80)
    print("Database tables")
    print("=" * 80)

    if not tables:
        print("No tables found.")
        return

    for table_name in tables:
        print(f"\n{table_name}")
        print("-" * len(table_name))

        columns = inspector.get_columns(table_name)

        for column in columns:
            column_name = column["name"]
            column_type = column["type"]
            nullable = column["nullable"]

            print(f"- {column_name}: {column_type} nullable={nullable}")


if __name__ == "__main__":
    main()