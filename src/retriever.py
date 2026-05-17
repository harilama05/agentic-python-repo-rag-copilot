import re
from dataclasses import dataclass
from typing import Any, Dict, List

from rank_bm25 import BM25Okapi

from src.vector_store import CodeVectorStore, SearchResult

from src.settings import (
    BM25_WEIGHT,
    DEFAULT_CANDIDATE_K,
    DEFAULT_TOP_K,
    KEYWORD_WEIGHT,
    SYMBOL_WEIGHT,
    VECTOR_WEIGHT,
)

@dataclass
class CodeSearchResult:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float
    bm25_score: float
    keyword_score: float
    symbol_score: float
    final_score: float


def _tokenize(text: str) -> List[str]:
    """
    Simple tokenizer for natural language and code identifiers.
    Splits snake_case and non-alphanumeric characters.
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

    if "function" in query_tokens and symbol_type in {"function", "async_function"}:
        score += 0.25

    if "class" in query_tokens and symbol_type == "class":
        score += 0.25

    if "method" in query_tokens and symbol_type in {"method", "async_method"}:
        score += 0.25

    return min(score, 1.0)


def _normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [0.0 for _ in scores]

    return [(score - min_score) / (max_score - min_score) for score in scores]


class CodeRetriever:
    """
    Hybrid retriever:
    - vector search from ChromaDB
    - BM25 lexical scoring
    - keyword overlap scoring
    - symbol-aware scoring
    """

    def __init__(self, vector_store: CodeVectorStore):
        self.vector_store = vector_store

    def search_code(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
    ) -> List[CodeSearchResult]:
        vector_results: List[SearchResult] = self.vector_store.search(
            query=query,
            top_k=candidate_k,
        )

        if not vector_results:
            return []

        documents = [result.text for result in vector_results]
        tokenized_documents = [_tokenize(doc) for doc in documents]
        tokenized_query = _tokenize(query)

        bm25 = BM25Okapi(tokenized_documents)
        raw_bm25_scores = bm25.get_scores(tokenized_query).tolist()
        normalized_bm25_scores = _normalize_scores(raw_bm25_scores)

        reranked: List[CodeSearchResult] = []

        for result, bm25_score in zip(vector_results, normalized_bm25_scores):
            keyword_score = _score_keyword_match(query, result.text)
            symbol_score = _score_symbol_match(query, result.metadata)

            final_score = (
                VECTOR_WEIGHT * result.score
                + BM25_WEIGHT * bm25_score
                + SYMBOL_WEIGHT * symbol_score
                + KEYWORD_WEIGHT * keyword_score
            )

            reranked.append(
                CodeSearchResult(
                    chunk_id=result.chunk_id,
                    text=result.text,
                    metadata=result.metadata,
                    vector_score=result.score,
                    bm25_score=bm25_score,
                    keyword_score=keyword_score,
                    symbol_score=symbol_score,
                    final_score=final_score,
                )
            )

        reranked.sort(key=lambda item: item.final_score, reverse=True)

        return reranked[:top_k]