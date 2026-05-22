"""Auto-discovered company repository catalog.

Company repositories are persistent repositories managed by the project owner.

To add a new company repository:

1. Copy the repository into company_repos/<repo_id>
2. Optionally create company_repos/<repo_id>/repo_config.json
3. Run: python -m scripts.index_company_repo <repo_id>

No Python code changes are required when adding a new company repository.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from src.core.config import COMPANY_REPOS_DIR


COMPANY_REPOS_ROOT = COMPANY_REPOS_DIR


@dataclass
class CompanyRepo:
    """One internally configured company repository."""

    repo_id: str
    name: str
    path: Path
    description: str


def make_display_name(repo_id: str) -> str:
    """Create a readable display name from a folder/repo id."""
    words = repo_id.replace("-", "_").split("_")
    display_words: list[str] = []

    for word in words:
        lower_word = word.lower()

        if lower_word == "api":
            display_words.append("API")
        elif lower_word == "rag":
            display_words.append("RAG")
        elif lower_word == "llm":
            display_words.append("LLM")
        elif lower_word == "ui":
            display_words.append("UI")
        else:
            display_words.append(word.capitalize())

    return " ".join(display_words)


def read_repo_config(repo_path: Path) -> dict[str, Any]:
    """Read optional repo_config.json from a company repository folder."""
    config_path = repo_path / "repo_config.json"

    if not config_path.exists():
        return {}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def discover_company_repos() -> Dict[str, CompanyRepo]:
    """Discover company repositories from the company_repos directory."""
    repos: Dict[str, CompanyRepo] = {}

    if not COMPANY_REPOS_ROOT.exists():
        return repos

    for repo_path in sorted(COMPANY_REPOS_ROOT.iterdir()):
        if not repo_path.is_dir():
            continue

        if repo_path.name.startswith("."):
            continue

        repo_id = repo_path.name
        config = read_repo_config(repo_path)

        repo_name = str(config.get("name") or make_display_name(repo_id)).strip()
        if not repo_name:
            repo_name = make_display_name(repo_id)

        description = str(config.get("description") or repo_name).strip()
        if not description:
            description = repo_name

        repos[repo_id] = CompanyRepo(
            repo_id=repo_id,
            name=repo_name,
            path=repo_path,
            description=description,
        )

    return repos


def get_company_repo_options() -> Dict[str, str]:
    """Return a display-name to repo-id mapping for internal scripts."""
    return {
        repo.name: repo_id
        for repo_id, repo in discover_company_repos().items()
    }


def get_company_repo(repo_id: str) -> CompanyRepo:
    """Return one discovered company repository by id."""
    repos = discover_company_repos()

    if repo_id not in repos:
        available = ", ".join(sorted(repos)) or "(none)"
        raise KeyError(
            f"Unknown company repo: {repo_id}. "
            f"Available company repo IDs: {available}"
        )

    return repos[repo_id]