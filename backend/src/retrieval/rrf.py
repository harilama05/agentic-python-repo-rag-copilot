"""Reciprocal Rank Fusion (RRF) scoring utilities.

RRF fuses multiple ranked lists into a single score per item using ranks rather
than raw scores. This is useful when combining signals from different retrieval
systems (vector search, BM25, metadata search, etc.).
"""

from typing import Dict


def rrf_fuse(*, ranked_lists: list[list[str]], rrf_k: int) -> Dict[str, float]:
    """Fuse multiple ranked lists into RRF scores.

    Args:
        ranked_lists: A list of ranked lists. Each inner list contains item IDs
            ordered from most relevant (rank 1) to least relevant.
        rrf_k: RRF constant. Larger values dampen the impact of top ranks.

    Returns:
        A mapping {item_id: rrf_score}.

    Notes:
        This implementation intentionally matches the previous inlined behavior
        to avoid tie-breaking changes.
    """
    scores: Dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            if not chunk_id:
                continue

            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)

    return scores
