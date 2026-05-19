"""Core filesystem and runtime path configuration."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
REPOS_DIR = DATA_DIR / "repos"
INDEX_DIR = DATA_DIR / "indexes"
RUNTIME_DIR = DATA_DIR / "runtime"

EXAMPLES_DIR = PROJECT_ROOT / "examples"
COMPANY_REPOS_DIR = EXAMPLES_DIR / "company_repos"

EVAL_CASES_PATH = DATA_DIR / "eval_cases.json"

RUNTIME_REPOS_DIR = RUNTIME_DIR / "repos"
RUNTIME_UPLOADS_DIR = RUNTIME_DIR / "uploads"
RUNTIME_GITHUB_DIR = RUNTIME_DIR / "github"


def ensure_data_dirs() -> None:
    """Ensure all runtime and data directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_REPOS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_GITHUB_DIR.mkdir(parents=True, exist_ok=True)
