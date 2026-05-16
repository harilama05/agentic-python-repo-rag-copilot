"""
BM25-based keyword store for lexical search.

Uses ``rank_bm25`` and persists the tokenised corpus to disk as JSON
so it survives restarts.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from src.config import settings
from src.schemas import Chunk, SearchResult


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return [t.lower() for t in text.split() if t.strip()]


class KeywordStore:
    """
    BM25Okapi-based keyword search over chunk texts.

    Persists the corpus and metadata as JSON files.
    """

    def __init__(self, persist_dir: str | Path | None = None):
        self._persist_dir = Path(persist_dir or settings.bm25_persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._corpus_file = self._persist_dir / "bm25_corpus.json"
        self._corpus: List[Dict[str, Any]] = []
        self._tokenized: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None

        self._load()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        if self._corpus_file.exists():
            try:
                self._corpus = json.loads(
                    self._corpus_file.read_text("utf-8")
                )
                self._tokenized = [_tokenize(item["text"]) for item in self._corpus]
                if self._tokenized:
                    self._bm25 = BM25Okapi(self._tokenized)
            except (json.JSONDecodeError, KeyError, OSError):
                self._corpus = []

    def save(self) -> None:
        self._corpus_file.write_text(
            json.dumps(self._corpus, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Indexing ─────────────────────────────────────────────────────

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """Add chunks to the BM25 corpus."""
        for chunk in chunks:
            self._corpus.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                }
            )
            self._tokenized.append(_tokenize(chunk.text))

        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)

    def reset(self) -> None:
        self._corpus = []
        self._tokenized = []
        self._bm25 = None
        if self._corpus_file.exists():
            self._corpus_file.unlink()

    # ── Search ───────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        BM25 keyword search.

        Returns results sorted by descending BM25 score.
        """
        if self._bm25 is None or not self._corpus:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Get top-k indices
        scored_indices: List[Tuple[int, float]] = [
            (i, float(s)) for i, s in enumerate(scores) if s > 0
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        scored_indices = scored_indices[:top_k]

        results: List[SearchResult] = []
        for idx, score in scored_indices:
            item = self._corpus[idx]
            results.append(
                SearchResult(
                    chunk_id=item["chunk_id"],
                    text=item["text"],
                    metadata=item.get("metadata", {}),
                    score=score,
                )
            )

        return results

    @property
    def count(self) -> int:
        return len(self._corpus)
