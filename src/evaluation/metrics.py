"""
Custom evaluation metrics for the RAG pipeline.

Includes:
- Answer relevancy (keyword overlap heuristic)
- Retrieval precision (source match)
- Faithfulness (basic grounding check)
"""

import re
from typing import List, Set


def _tokenize(text: str) -> Set[str]:
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return {t.lower() for t in text.split() if len(t) > 1}


def answer_relevancy(question: str, answer: str) -> float:
    """
    Heuristic: fraction of question keywords present in the answer.
    """
    q_tokens = _tokenize(question)
    a_tokens = _tokenize(answer)

    if not q_tokens:
        return 0.0

    overlap = q_tokens & a_tokens
    return len(overlap) / len(q_tokens)


def retrieval_precision(
    expected_sources: List[str],
    retrieved_sources: List[str],
) -> float:
    """
    Precision: fraction of retrieved sources that are relevant.
    """
    if not retrieved_sources:
        return 0.0

    expected_set = {s.lower() for s in expected_sources}
    hits = sum(1 for s in retrieved_sources if s.lower() in expected_set)
    return hits / len(retrieved_sources)


def retrieval_recall(
    expected_sources: List[str],
    retrieved_sources: List[str],
) -> float:
    """
    Recall: fraction of expected sources that were retrieved.
    """
    if not expected_sources:
        return 1.0  # Nothing to recall

    expected_set = {s.lower() for s in expected_sources}
    retrieved_set = {s.lower() for s in retrieved_sources}
    hits = len(expected_set & retrieved_set)
    return hits / len(expected_set)


def faithfulness(answer: str, context: str) -> float:
    """
    Heuristic faithfulness: fraction of answer tokens grounded in context.
    """
    a_tokens = _tokenize(answer)
    c_tokens = _tokenize(context)

    if not a_tokens:
        return 1.0

    grounded = a_tokens & c_tokens
    return len(grounded) / len(a_tokens)


def compute_metrics(
    question: str,
    answer: str,
    context: str,
    expected_sources: List[str],
    retrieved_sources: List[str],
) -> dict:
    """Compute all metrics and return as a dictionary."""
    return {
        "answer_relevancy": round(answer_relevancy(question, answer), 4),
        "retrieval_precision": round(retrieval_precision(expected_sources, retrieved_sources), 4),
        "retrieval_recall": round(retrieval_recall(expected_sources, retrieved_sources), 4),
        "faithfulness": round(faithfulness(answer, context), 4),
    }
