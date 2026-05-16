from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class CompanyRepo:
    repo_id: str
    name: str
    path: Path
    description: str


COMPANY_REPOS: Dict[str, CompanyRepo] = {
    "taskflow_api": CompanyRepo(
        repo_id="taskflow_api",
        name="TaskFlow API",
        path=Path("examples/company_repos/taskflow_api"),
        description="Python backend service for managing tasks and team work items.",
    ),
}


def get_company_repo_options() -> Dict[str, str]:
    return {
        repo.name: repo_id
        for repo_id, repo in COMPANY_REPOS.items()
    }


def get_company_repo(repo_id: str) -> CompanyRepo:
    return COMPANY_REPOS[repo_id]