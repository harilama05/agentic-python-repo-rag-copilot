"""
Maximal Marginal Relevance (MMR) — diversifies search results by
penalising redundancy among top results.

``MMR(d) = λ · sim(d, query) - (1-λ) · max(sim(d, d_selected))``
"""

import numpy as np
from typing import List

from src.schemas import SearchResult
from src.embeddings.embedding_model import EmbeddingModel


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def mmr_rerank(
    query: str,
    results: List[SearchResult],
    embedding_model: EmbeddingModel,
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> List[SearchResult]:
    """
    Apply MMR to diversify the top-k results.

    Args:
        query: The user query.
        results: Pre-ranked search results.
        embedding_model: Model to compute embeddings for similarity.
        top_k: Number of results to return.
        lambda_param: Balance between relevance (1.0) and diversity (0.0).

    Returns:
        Re-ordered results with reduced redundancy.
    """
    if len(results) <= 1:
        return results[:top_k]

    # Embed query and all documents
    query_emb = np.array(embedding_model.embed_query(query))
    doc_texts = [r.text for r in results]
    doc_embs = [np.array(e) for e in embedding_model.embed_texts(doc_texts, show_progress=False)]

    # Precompute query-doc similarities
    query_sims = [_cosine_sim(query_emb, d) for d in doc_embs]

    selected_indices: List[int] = []
    remaining = list(range(len(results)))

    for _ in range(min(top_k, len(results))):
        best_idx = -1
        best_score = float("-inf")

        for idx in remaining:
            relevance = query_sims[idx]

            # Max similarity to already-selected docs
            if selected_indices:
                max_redundancy = max(
                    _cosine_sim(doc_embs[idx], doc_embs[s])
                    for s in selected_indices
                )
            else:
                max_redundancy = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx >= 0:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    return [results[i] for i in selected_indices]
