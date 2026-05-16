from app.services.task_service import TaskService


def list_tasks() -> list[dict]:
    service = TaskService()
    return service.list_tasks()


def create_task(title: str, assignee: str) -> dict:
    service = TaskService()
    return service.create_task(title=title, assignee=assignee)