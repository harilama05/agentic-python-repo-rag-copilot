from src.storage.lifecycle.deletion import delete_repository
from src.storage.lifecycle.queries import list_expired_temporary_repositories

def cleanup_temporary_repository(repo_id: str | None) -> bool:
    if not repo_id:
        return False
    return delete_repository(
        repo_id=repo_id,
        delete_runtime_files=True,
        only_if_temporary=True,
    )

def cleanup_expired_temporary_repositories(
    *,
    dry_run: bool = False,
) -> list[str]:
    expired_repos = list_expired_temporary_repositories()
    repo_ids: list[str] = []
    for repo in expired_repos:
        repo_ids.append(repo.repo_id)
        if dry_run:
            continue
        delete_repository(
            repo_id=repo.repo_id,
            delete_runtime_files=True,
            only_if_temporary=True,
        )
    return repo_ids
