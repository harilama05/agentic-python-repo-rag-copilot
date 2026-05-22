"""Reranking package for post-retrieval result ordering.

Fast mode uses a no-op reranker.
Accurate mode uses a Cross-Encoder to rescore candidate chunks.
"""

from src.reranking.reranker import NoOpReranker, Reranker
from src.reranking.cross_encoder_reranker import CrossEncoderReranker

__all__ = ["Reranker", "NoOpReranker", "CrossEncoderReranker"]
