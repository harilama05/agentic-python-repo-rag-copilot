# Query types
QUERY_TYPE_DOCUMENTATION = "documentation_query"
QUERY_TYPE_LOCATION = "location_query"
QUERY_TYPE_REFERENCE = "reference_query"
QUERY_TYPE_EXPLANATION = "explanation_query"
QUERY_TYPE_SEARCH = "search_query"
QUERY_TYPE_IMPACT = "impact_query"
QUERY_TYPE_CALLER = "caller_query"
QUERY_TYPE_CALLEE = "callee_query"
QUERY_TYPE_FLOW = "flow_query"


# Source types
SOURCE_TYPE_CODE = "code"
SOURCE_TYPE_DOC = "doc"


# Symbol / chunk types
SYMBOL_TYPE_DOCUMENTATION = "documentation"


# File extensions
PYTHON_EXTENSIONS = {".py"}
DOC_EXTENSIONS = {".md", ".markdown"}


# Repository folders to ignore
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "node_modules",
}


# Repo source types
REPO_SOURCE_COMPANY = "company"
REPO_SOURCE_GITHUB = "github"
REPO_SOURCE_ZIP = "zip"
REPO_SOURCE_CUSTOM_LOCAL = "custom_local"