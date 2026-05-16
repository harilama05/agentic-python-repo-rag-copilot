class TaskService:
    def list_tasks(self) -> list[dict]:
        return [
            {
                "id": 1,
                "title": "Review onboarding guide",
                "status": "open",
            }
        ]

    def create_task(self, title: str, assignee: str) -> dict:
        return {
            "id": 2,
            "title": title,
            "assignee": assignee,
            "status": "open",
        }