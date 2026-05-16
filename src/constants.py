"""
Các hằng số cho Agentic RAG Codebase Assistant.
"""

# ── Các đuôi file hỗ trợ ────────────────────────────────────────
SUPPORTED_CODE_EXTENSIONS = {".py"}

SUPPORTED_DOC_EXTENSIONS = {".md", ".txt", ".rst"}

SUPPORTED_CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml"}

SUPPORTED_EXTENSIONS = (
    SUPPORTED_CODE_EXTENSIONS | SUPPORTED_DOC_EXTENSIONS | SUPPORTED_CONFIG_EXTENSIONS
)

# ── Các thư mục cần ignore khi quét ────────────────────────────
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".tox",
    ".nox",
}

# ── Mặc định chunk size ────────────────────────────────────────────────
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
MAX_CHUNK_SIZE = 2048

# ── Mặc định retrieval ─────────────────────────────────────────────
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_K = 30
DEFAULT_RERANK_TOP_K = 5

# ── Hằng số RRF ─────────────────────────────────────────────────────
RRF_K = 60

# ── Embedding model mặc định ─────────────────────────────────────────
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# ── Cross‑encoder model mặc định ─────────────────────────────────────
DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# ── LLM mặc định ─────────────────────────────────────────────────────
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_TEMPERATURE = 0.1
DEFAULT_LLM_MAX_TOKENS = 2048

# ── Upload limits ────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = 10
ALLOWED_UPLOAD_EXTENSIONS = SUPPORTED_EXTENSIONS

# ── Metadata keys ────────────────────────────────────────────────────
META_FILE_PATH = "file_path"
META_RELATIVE_PATH = "relative_path"
META_SYMBOL_NAME = "symbol_name"
META_QUALIFIED_NAME = "qualified_name"
META_SYMBOL_TYPE = "symbol_type"
META_START_LINE = "start_line"
META_END_LINE = "end_line"
META_PARENT = "parent"
META_DOCSTRING = "docstring"
META_LANGUAGE = "language"
META_SOURCE = "source"  # "repo" or "upload"
META_CHUNK_TYPE = "chunk_type"  # "code", "text", "markdown"
