from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPOS_DIR = DATA_DIR / "repos"
INDEX_DIR = DATA_DIR / "indexes"

SUPPORTED_EXTENSIONS = {".py"}

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
}