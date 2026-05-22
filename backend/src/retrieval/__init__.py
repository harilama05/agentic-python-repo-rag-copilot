"""Retrieval package for hybrid code/documentation search.

This package contains the retrieval pipeline used by the application, including
multi-source retrieval and Reciprocal Rank Fusion (RRF).
"""

from src.retrieval.retriever import CodeRetriever, CodeSearchResult

__all__ = ["CodeRetriever", "CodeSearchResult"]
