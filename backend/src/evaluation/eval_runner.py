"""Evaluation models and metrics for agent responses."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src.agent_core.response_models import AgentResponse
from src.evaluation.metrics import (
    answer_non_empty as compute_answer_non_empty,
    compute_abstention_correct,
    compute_file_hit_rate,
    compute_keyword_recall,
    compute_source_precision,
    has_forbidden_keywords,
    is_llm_failure,
    is_router_fallback,
    safe_average,
    source_matches as metric_source_matches,
)


@dataclass
class EvalCase:
    """One evaluation case for repository QA."""

    id: str
    repo_id: str
    repo_path: str
    question: str
    expected_query_type: str
    expected_sources: List[str]
    expected_files: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    requires_abstention: bool = False
    question_type: str = ""
    difficulty: str = ""
    reference_answer: str | None = None
    max_latency_seconds: float | None = None


@dataclass
class EvalResult:
    """One evaluation result after executing an eval case."""

    id: str
    repo_id: str
    repo_path: str
    question: str
    expected_query_type: str
    actual_query_type: str
    query_type_correct: bool
    expected_sources: List[str]
    actual_sources: List[str]
    source_hit_count: int
    source_recall: float
    expected_sources_all_found: bool
    answer: str
    source_precision: float = 0.0
    file_hit_rate: float = 1.0
    answer_non_empty: bool = False
    answer_keyword_recall: float = 1.0
    forbidden_keyword_hit: bool = False
    abstention_correct: bool | None = None
    citation_validity_rate: float | None = None
    latency_seconds: float | None = None
    router_fallback: bool = False
    llm_failure: bool = False


def load_eval_cases(path: str | Path) -> List[EvalCase]:
    """Load evaluation cases from a JSON file."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = []

    for item in data:
        cases.append(
            EvalCase(
                id=item["id"],
                repo_id=item["repo_id"],
                repo_path=item["repo_path"],
                question=item["question"],
                expected_query_type=item["expected_query_type"],
                expected_sources=item.get("expected_sources", []),
                expected_files=item.get("expected_files", []),
                expected_keywords=item.get("expected_keywords", []),
                forbidden_keywords=item.get("forbidden_keywords", []),
                requires_abstention=item.get("requires_abstention", False),
                question_type=item.get("question_type", ""),
                difficulty=item.get("difficulty", ""),
                reference_answer=item.get("reference_answer"),
                max_latency_seconds=item.get("max_latency_seconds"),
            )
        )

    return cases


def normalize_path(path: str) -> str:
    """Normalize path separators for comparison."""
    return path.replace("\\", "/").strip()


def normalize_source(source: str) -> str:
    """Normalize source citation strings for comparison."""
    return normalize_path(source)


def source_from_agent_source(source: Dict[str, Any]) -> str:
    """Build a compact source string from agent source metadata."""
    relative_path = normalize_path(str(source.get("relative_path", "")))
    line_start = source.get("line_start")
    line_end = source.get("line_end")

    if line_start is None:
        return relative_path

    if line_end is None or line_start == line_end:
        return f"{relative_path}:{line_start}"

    return f"{relative_path}:{line_start}-{line_end}"


def get_actual_sources(response: AgentResponse) -> List[str]:
    """Return normalized source strings from an agent response."""
    return [source_from_agent_source(source) for source in response.sources]


def _parse_line_range(line_text: str) -> tuple[int, int]:
    if "-" in line_text:
        start, end = line_text.split("-", 1)
        return int(start), int(end)

    line = int(line_text)
    return line, line


def source_matches(expected: str, actual: str) -> bool:
    """Return True when an actual source satisfies an expected source citation."""
    return metric_source_matches(expected, actual)


def evaluate_response(
    case: EvalCase,
    response: AgentResponse,
    latency_seconds: float | None = None,
    raw_results: dict[str, Any] | None = None,
    citation_validity_rate: float | None = None,
) -> EvalResult:
    """Evaluate one agent response against one eval case."""
    actual_sources = get_actual_sources(response)
    query_type_correct = response.query_type == case.expected_query_type
    hit_count = 0
    answer = response.answer

    for expected_source in case.expected_sources:
        if any(source_matches(expected_source, actual) for actual in actual_sources):
            hit_count += 1

    if case.expected_sources:
        source_recall = hit_count / len(case.expected_sources)
    else:
        source_recall = 1.0

    expected_sources_all_found = hit_count == len(case.expected_sources)
    effective_raw_results = (
        raw_results
        if raw_results is not None
        else getattr(response, "raw_results", None)
    )

    return EvalResult(
        id=case.id,
        repo_id=case.repo_id,
        repo_path=case.repo_path,
        question=case.question,
        expected_query_type=case.expected_query_type,
        actual_query_type=response.query_type,
        query_type_correct=query_type_correct,
        expected_sources=case.expected_sources,
        actual_sources=actual_sources,
        source_hit_count=hit_count,
        source_recall=source_recall,
        expected_sources_all_found=expected_sources_all_found,
        answer=answer,
        source_precision=compute_source_precision(
            actual_sources=actual_sources,
            expected_sources=case.expected_sources,
        ),
        file_hit_rate=compute_file_hit_rate(
            actual_sources=actual_sources,
            expected_files=case.expected_files,
        ),
        answer_non_empty=compute_answer_non_empty(answer),
        answer_keyword_recall=compute_keyword_recall(
            answer=answer,
            expected_keywords=case.expected_keywords,
        ),
        forbidden_keyword_hit=has_forbidden_keywords(
            answer=answer,
            forbidden_keywords=case.forbidden_keywords,
        ),
        abstention_correct=compute_abstention_correct(
            answer=answer,
            requires_abstention=case.requires_abstention,
        ),
        citation_validity_rate=citation_validity_rate,
        latency_seconds=latency_seconds,
        router_fallback=is_router_fallback(effective_raw_results),
        llm_failure=is_llm_failure(effective_raw_results),
    )


def summarize_eval_results(results: List[EvalResult]) -> Dict[str, float]:
    """Summarize aggregate evaluation metrics."""
    if not results:
        return {
            "num_cases": 0.0,
            "query_type_accuracy": 0.0,
            "avg_source_recall": 0.0,
            "expected_sources_all_found_rate": 0.0,
            "avg_source_precision": 0.0,
            "avg_file_hit_rate": 0.0,
            "answer_non_empty_rate": 0.0,
            "avg_answer_keyword_recall": 0.0,
            "forbidden_keyword_hit_rate": 0.0,
            "abstention_accuracy": 0.0,
            "avg_citation_validity_rate": 0.0,
            "avg_latency_seconds": 0.0,
            "router_fallback_rate": 0.0,
            "llm_failure_rate": 0.0,
        }

    num_cases = len(results)
    query_type_accuracy = sum(
        1 for result in results if result.query_type_correct
    ) / num_cases
    avg_source_recall = sum(
        result.source_recall for result in results
    ) / num_cases
    expected_sources_all_found_rate = sum(
        1 for result in results if result.expected_sources_all_found
    ) / num_cases
    avg_source_precision = sum(
        result.source_precision for result in results
    ) / num_cases
    avg_file_hit_rate = sum(
        result.file_hit_rate for result in results
    ) / num_cases
    answer_non_empty_rate = sum(
        1 for result in results if result.answer_non_empty
    ) / num_cases
    avg_answer_keyword_recall = sum(
        result.answer_keyword_recall for result in results
    ) / num_cases
    forbidden_keyword_hit_rate = sum(
        1 for result in results if result.forbidden_keyword_hit
    ) / num_cases
    abstention_values = [
        1.0 if result.abstention_correct else 0.0
        for result in results
        if result.abstention_correct is not None
    ]
    citation_validity_values = [
        result.citation_validity_rate
        for result in results
        if result.citation_validity_rate is not None
    ]
    latency_values = [
        result.latency_seconds
        for result in results
        if result.latency_seconds is not None
    ]
    router_fallback_rate = sum(
        1 for result in results if result.router_fallback
    ) / num_cases
    llm_failure_rate = sum(
        1 for result in results if result.llm_failure
    ) / num_cases

    return {
        "num_cases": float(num_cases),
        "query_type_accuracy": query_type_accuracy,
        "avg_source_recall": avg_source_recall,
        "expected_sources_all_found_rate": expected_sources_all_found_rate,
        "avg_source_precision": avg_source_precision,
        "avg_file_hit_rate": avg_file_hit_rate,
        "answer_non_empty_rate": answer_non_empty_rate,
        "avg_answer_keyword_recall": avg_answer_keyword_recall,
        "forbidden_keyword_hit_rate": forbidden_keyword_hit_rate,
        "abstention_accuracy": safe_average(abstention_values),
        "avg_citation_validity_rate": safe_average(citation_validity_values),
        "avg_latency_seconds": safe_average(latency_values),
        "router_fallback_rate": router_fallback_rate,
        "llm_failure_rate": llm_failure_rate,
    }
