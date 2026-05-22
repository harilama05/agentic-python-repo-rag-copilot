import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import os
import stat
import time
from src.core.config import RUNTIME_GITHUB_DIR


@dataclass
class IngestedGithubRepo:
    repo_id: str
    name: str
    github_url: str
    branch: str | None
    commit_hash: str | None
    local_path: Path


def _run_command(
    command: list[str],
    cwd: Path | None = None,
    timeout: int = 180,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(error)

    return result.stdout.strip()


def normalize_github_url(url: str) -> str:
    url = url.strip()

    if not url:
        raise ValueError("GitHub URL is required.")

    parsed = urlparse(url)

    if parsed.netloc.lower() != "github.com":
        raise ValueError("Only public github.com repositories are supported.")

    path = parsed.path.strip("/")

    if not path:
        raise ValueError("Invalid GitHub URL.")

    parts = path.split("/")

    if len(parts) < 2:
        raise ValueError("GitHub URL must include owner and repository name.")

    owner = parts[0]
    repo = parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return f"https://github.com/{owner}/{repo}.git"


def parse_github_repo(url: str) -> tuple[str, str]:
    normalized = normalize_github_url(url)
    parsed = urlparse(normalized)

    parts = parsed.path.strip("/").split("/")
    owner = parts[0]
    repo = parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def make_github_repo_id(github_url: str, branch: str | None = None) -> str:
    owner, repo = parse_github_repo(github_url)

    raw = f"{github_url}:{branch or 'default'}"
    suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]

    safe_owner = re.sub(r"[^a-zA-Z0-9_]+", "_", owner).lower()
    safe_repo = re.sub(r"[^a-zA-Z0-9_]+", "_", repo).lower()

    return f"github_{safe_owner}_{safe_repo}_{suffix}"

def _handle_remove_readonly(func, path, exc_info):
    """
    Windows-safe handler for shutil.rmtree.

    Git pack files can sometimes be read-only or temporarily locked.
    This tries to make the file writable and remove it again.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def safe_rmtree(path: Path, retries: int = 3, delay_seconds: float = 0.5) -> None:
    """
    Remove a directory robustly on Windows.

    Useful for deleting cloned Git repositories where .git/objects/pack files
    may be read-only or briefly locked.
    """
    if not path.exists():
        return

    last_error = None

    for _ in range(retries):
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay_seconds)

    raise last_error

def clone_github_repo(
    github_url: str,
    branch: str | None = None,
    force_refresh: bool = True,
) -> IngestedGithubRepo:
    normalized_url = normalize_github_url(github_url)
    owner, repo = parse_github_repo(normalized_url)

    repo_id = make_github_repo_id(normalized_url, branch=branch)
    target_dir = RUNTIME_GITHUB_DIR / repo_id

    RUNTIME_GITHUB_DIR.mkdir(parents=True, exist_ok=True)

    if target_dir.exists() and force_refresh:
        safe_rmtree(target_dir)

    if not target_dir.exists():
        command = [
            "git",
            "clone",
            "--depth",
            "1",
        ]

        if branch:
            command.extend(["--branch", branch])

        command.extend([normalized_url, str(target_dir)])

        _run_command(command, timeout=240)

    commit_hash = None

    try:
        commit_hash = _run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=target_dir,
            timeout=30,
        )
    except RuntimeError:
        commit_hash = None

    return IngestedGithubRepo(
        repo_id=repo_id,
        name=repo,
        github_url=normalized_url,
        branch=branch,
        commit_hash=commit_hash,
        local_path=target_dir,
    )
