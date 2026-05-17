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


# Upload / ingestion settings, reserved for later
MAX_REPO_UPLOAD_MB = 100
MAX_GITHUB_REPO_MB = 100

import os
from dotenv import load_dotenv

load_dotenv(override=True)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "code_chunks")