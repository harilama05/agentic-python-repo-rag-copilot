"""
Cấu hình ứng dụng được load từ environment variables.

Sử dụng pydantic-settings cho config type-safe và validated với .env support.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import (
    DEFAULT_CROSS_ENCODER_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TEMPERATURE,
)


class Settings(BaseSettings):
    """Cấu hình trung tâm cho toàn bộ ứng dụng."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Paths ─────────────────────────────────────────────────────────
    project_root: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    repos_dir: Path = Path(__file__).resolve().parents[1] / "data" / "repos"
    uploads_dir: Path = Path(__file__).resolve().parents[1] / "data" / "uploads"
    index_dir: Path = Path(__file__).resolve().parents[1] / "data" / "indexes"
    logs_dir: Path = Path(__file__).resolve().parents[1] / "data" / "logs"
    eval_dir: Path = Path(__file__).resolve().parents[1] / "data" / "eval"

    # ── Embedding ────────────────────────────────────────────────────
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL

    # ── Cross‑encoder ────────────────────────────────────────────────
    cross_encoder_model_name: str = DEFAULT_CROSS_ENCODER_MODEL

    # ── LLM ──────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = None
    openai_api_base_url: Optional[str] = None
    llm_model: str = DEFAULT_LLM_MODEL
    llm_temperature: float = DEFAULT_LLM_TEMPERATURE
    llm_max_tokens: int = DEFAULT_LLM_MAX_TOKENS

    # ── ChromaDB ─────────────────────────────────────────────────────
    chroma_persist_dir: Path = Path(__file__).resolve().parents[1] / "data" / "indexes" / "chroma"
    chroma_collection_name: str = "codebase_chunks"

    # ── BM25 ─────────────────────────────────────────────────────────
    bm25_persist_dir: Path = Path(__file__).resolve().parents[1] / "data" / "indexes" / "bm25"

    # ── Metadata store ───────────────────────────────────────────────
    metadata_persist_dir: Path = Path(__file__).resolve().parents[1] / "data" / "indexes" / "metadata"
    graph_persist_dir: Path = Path(__file__).resolve().parents[1] / "data" / "indexes" / "graph"

    def ensure_dirs(self) -> None:
        """Tạo tất cả các thư mục cần thiết."""
        for d in [
            self.data_dir,
            self.repos_dir,
            self.uploads_dir,
            self.index_dir,
            self.logs_dir,
            self.eval_dir,
            self.chroma_persist_dir,
            self.bm25_persist_dir,
            self.metadata_persist_dir,
            self.graph_persist_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)


# Singleton settings instance
settings = Settings()
