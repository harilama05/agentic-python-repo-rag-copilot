import re
from dataclasses import dataclass
from typing import Any, Dict, List

from src.vector_store import CodeVectorStore, SearchResult


@dataclass
class CodeSearchResult:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float
    keyword_score: float
    symbol_score: float
    final_score: float


def _tokenize(text: str) -> List[str]:
    """
    Simple tokenizer for natural language and code identifiers.
    """
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return [token.lower() for token in text.split() if token.strip()]


def _score_keyword_match(query: str, document: str) -> float:
    query_tokens = set(_tokenize(query))
    document_tokens = set(_tokenize(document))

    if not query_tokens:
        return 0.0

    overlap = query_tokens.intersection(document_tokens)
    return len(overlap) / len(query_tokens)


def _score_symbol_match(query: str, metadata: Dict[str, Any]) -> float:
    query_tokens = set(_tokenize(query))

    symbol_name = str(metadata.get("symbol_name", ""))
    qualified_name = str(metadata.get("qualified_name", ""))
    symbol_type = str(metadata.get("symbol_type", ""))

    symbol_text = f"{symbol_name} {qualified_name} {symbol_type}"
    symbol_tokens = set(_tokenize(symbol_text))

    if not query_tokens:
        return 0.0

    overlap = query_tokens.intersection(symbol_tokens)
    score = len(overlap) / len(query_tokens)

    # Extra boost if the query seems to ask for a function/class/method
    # and the chunk type matches.
    if "function" in query_tokens and symbol_type in {"function", "async_function"}:
        score += 0.25

    if "class" in query_tokens and symbol_type == "class":
        score += 0.25

    if "method" in query_tokens and symbol_type in {"method", "async_method"}:
        score += 0.25

    return min(score, 1.0)


class CodeRetriever:
    """
    Hybrid-ish retriever:
    - gets candidates from vector search
    - reranks using keyword overlap and symbol metadata
    """

    def __init__(self, vector_store: CodeVectorStore):
        self.vector_store = vector_store

    def search_code(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
    ) -> List[CodeSearchResult]:
        vector_results: List[SearchResult] = self.vector_store.search(
            query=query,
            top_k=candidate_k,
        )

        reranked: List[CodeSearchResult] = []

        for result in vector_results:
            keyword_score = _score_keyword_match(query, result.text)
            symbol_score = _score_symbol_match(query, result.metadata)

            # Vector score from Chroma can be small/negative depending on distance.
            # We combine it with stronger symbolic signals for code search.
            final_score = (
                0.45 * result.score
                + 0.25 * keyword_score
                + 0.30 * symbol_score
            )

            reranked.append(
                CodeSearchResult(
                    chunk_id=result.chunk_id,
                    text=result.text,
                    metadata=result.metadata,
                    vector_score=result.score,
                    keyword_score=keyword_score,
                    symbol_score=symbol_score,
                    final_score=final_score,
                )
            )

        reranked.sort(key=lambda item: item.final_score, reverse=True)

        return reranked[:top_k]