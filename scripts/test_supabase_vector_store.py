from dataclasses import dataclass, field
from typing import Any

from src.storage.supabase_vector_store import SupabaseCodeVectorStore


@dataclass
class FakeChunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def main() -> None:
    repo_id = "test_supabase_repo"

    store = SupabaseCodeVectorStore(repo_id=repo_id)
    store.reset_collection()

    chunks = [
        FakeChunk(
            text="def create_task(title, assignee): service = TaskService(); return service.create_task(title, assignee)",
            metadata={
                "source_type": "code",
                "relative_path": "app/api/tasks.py",
                "start_line": 9,
                "end_line": 11,
                "symbol_name": "create_task",
                "qualified_name": "create_task",
                "symbol_type": "function",
            },
        ),
        FakeChunk(
            text="class TaskService: def create_task(self, title, assignee): return {'title': title, 'assignee': assignee}",
            metadata={
                "source_type": "code",
                "relative_path": "app/services/task_service.py",
                "start_line": 11,
                "end_line": 17,
                "symbol_name": "create_task",
                "qualified_name": "TaskService.create_task",
                "symbol_type": "method",
            },
        ),
    ]

    store.add_chunks(chunks)

    results = store.search_text(
        query="task creation method",
        top_k=5,
    )

    print("=" * 100)
    print("Supabase vector search results")
    print("=" * 100)

    for result in results:
        print(
            f"{result['score']:.4f} | "
            f"{result['relative_path']}:{result['start_line']}-{result['end_line']} | "
            f"{result['qualified_name']}"
        )


if __name__ == "__main__":
    main()
