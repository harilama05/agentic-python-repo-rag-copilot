"""Evaluation models and metrics for agent responses."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.agent_core.response_models import AgentResponse


@dataclass
class EvalCase:
    """One evaluation case for repository QA."""

    id: str
    repo_id: str
    repo_path: str
    question: str
    expected_query_type: str
    expected_sources: List[str]


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
                expected_sources=item["expected_sources"],
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
    expected = normalize_source(expected)
    actual = normalize_source(actual)

    if expected == actual:
        return True

    if ":" not in expected or ":" not in actual:
        return False

    expected_path, expected_lines = expected.rsplit(":", 1)
    actual_path, actual_lines = actual.rsplit(":", 1)

    if expected_path != actual_path:
        return False

    try:
        expected_start, expected_end = _parse_line_range(expected_lines)
        actual_start, actual_end = _parse_line_range(actual_lines)
    except ValueError:
        return False

    return actual_start <= expected_start and expected_end <= actual_end


def evaluate_response(case: EvalCase, response: AgentResponse) -> EvalResult:
    """Evaluate one agent response against one eval case."""
    actual_sources = get_actual_sources(response)
    query_type_correct = response.query_type == case.expected_query_type
    hit_count = 0

    for expected_source in case.expected_sources:
        if any(source_matches(expected_source, actual) for actual in actual_sources):
            hit_count += 1

    if case.expected_sources:
        source_recall = hit_count / len(case.expected_sources)
    else:
        source_recall = 1.0

    expected_sources_all_found = hit_count == len(case.expected_sources)

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
        answer=response.answer,
    )


def summarize_eval_results(results: List[EvalResult]) -> Dict[str, float]:
    """Summarize aggregate evaluation metrics."""
    if not results:
        return {
            "num_cases": 0.0,
            "query_type_accuracy": 0.0,
            "avg_source_recall": 0.0,
            "expected_sources_all_found_rate": 0.0,
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

    return {
        "num_cases": float(num_cases),
        "query_type_accuracy": query_type_accuracy,
        "avg_source_recall": avg_source_recall,
        "expected_sources_all_found_rate": expected_sources_all_found_rate,
    }
