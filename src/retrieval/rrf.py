"""
Reciprocal Rank Fusion (RRF) — combines ranked lists from multiple
search strategies into a single fused ranking.

Reference: Cormack, Clarke & Buettcher (2009)
    ``score(d) = Σ 1 / (k + rank_i(d))``
"""

from typing import Dict, List

from src.constants import RRF_K
from src.schemas import SearchResult


def reciprocal_rank_fusion(
    ranked_lists: List[List[SearchResult]],
    k: int = RRF_K,
    top_k: int = 10,
) -> List[SearchResult]:
    """
    Fuse multiple ranked lists using RRF.

    Args:
        ranked_lists: A list of ranked result lists from different strategies.
        k: Smoothing constant (default 60 from the paper).
        top_k: Number of results to return.

    Returns:
        Fused results sorted by descending RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + (
                1.0 / (k + rank)
            )
            # Keep the first occurrence (usually from the highest-quality source)
            if result.chunk_id not in chunk_map:
                chunk_map[result.chunk_id] = result

    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    fused: List[SearchResult] = []
    for chunk_id in sorted_ids[:top_k]:
        result = chunk_map[chunk_id]
        fused.append(
            SearchResult(
                chunk_id=result.chunk_id,
                text=result.text,
                content=result.content,
                metadata=result.metadata,
                score=rrf_scores[chunk_id],
            )
        )

    return fused
