# Embedding model
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# Retrieval defaults
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_K = 20


# Hybrid retrieval weights
VECTOR_WEIGHT = 0.40
BM25_WEIGHT = 0.30
SYMBOL_WEIGHT = 0.20
KEYWORD_WEIGHT = 0.10


# Documentation query defaults
DOCUMENTATION_TOP_K = 5
FALLBACK_SEARCH_TOP_K = 3

# Cross-encoder settings, reserved for later
DEFAULT_RETRIEVAL_MODE = "fast"
RETRIEVAL_MODE_FAST = "fast"
RETRIEVAL_MODE_ACCURATE = "accurate"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CROSS_ENCODER_CANDIDATE_K = 20
CROSS_ENCODER_TOP_K = 5


# Upload / ingestion settings, reserved for later
MAX_REPO_UPLOAD_MB = 100
MAX_GITHUB_REPO_MB = 100