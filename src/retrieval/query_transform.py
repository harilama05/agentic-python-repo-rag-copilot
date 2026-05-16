"""
Query transformation — rewrites user queries for better retrieval.

Techniques:
- Keyword extraction (strip stopwords)
- Query expansion via synonym / identifier heuristics
"""

import re
from typing import List, Optional

STOPWORDS = {
    "where", "is", "are", "the", "a", "an", "used", "use", "uses",
    "implemented", "defined", "located", "what", "does", "do",
    "explain", "how", "works", "work", "function", "class", "method",
    "in", "of", "to", "for", "and", "or", "with", "find", "show",
    "me", "can", "you", "this", "that", "tell", "about", "code",
    "related", "all", "get", "list",
}


def extract_keywords(question: str) -> List[str]:
    """
    Extract meaningful tokens from a natural-language question
    by removing stopwords.
    """
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", question)
    return [t for t in tokens if t.lower() not in STOPWORDS]


def extract_symbol_candidate(question: str) -> Optional[str]:
    """
    Extract the most likely symbol name from a question.

    Prefers backtick-quoted names, then snake_case, then CamelCase.
    """
    # Backtick-quoted
    backtick = re.search(r"`([^`]+)`", question)
    if backtick:
        return backtick.group(1).strip()

    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", question)
    candidates = []

    for token in tokens:
        if token.lower() in STOPWORDS:
            continue
        score = 0
        if "_" in token:
            score += 3  # snake_case → likely Python symbol
        if any(c.isupper() for c in token[1:]):
            score += 2  # CamelCase → likely class name
        score += 1
        candidates.append((score, token))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def classify_query(question: str) -> str:
    """
    Classify a user question into one of:
    - ``reference_query``: "Where is X used?"
    - ``location_query``: "Where is X defined?"
    - ``explanation_query``: "What does X do?"
    - ``search_query``: General code search
    """
    q = question.lower()

    if any(p in q for p in ["used", "called", "references", "referenced", "who calls"]):
        return "reference_query"

    if any(p in q for p in ["where is", "where are", "implemented", "defined", "located"]):
        return "location_query"

    if any(p in q for p in ["what does", "explain", "how does", "how do", "describe"]):
        return "explanation_query"

    return "search_query"
