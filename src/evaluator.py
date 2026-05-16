import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.agent import AgentResponse


@dataclass
class EvalCase:
    id: str
    question: str
    expected_query_type: str
    expected_sources: List[str]


@dataclass
class EvalResult:
    id: str
    question: str
    expected_query_type: str
    actual_query_type: str
    query_type_correct: bool
    expected_sources: List[str]
    actual_sources: List[str]
    source_hit_count: int
    source_recall: float
    exact_source_match: bool
    answer: str


def load_eval_cases(path: str | Path) -> List[EvalCase]:
    path = Path(path)

    data = json.loads(path.read_text(encoding="utf-8"))

    cases = []

    for item in data:
        cases.append(
            EvalCase(
                id=item["id"],
                question=item["question"],
                expected_query_type=item["expected_query_type"],
                expected_sources=item["expected_sources"],
            )
        )

    return cases


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def normalize_source(source: str) -> str:
    return normalize_path(source)


def source_from_agent_source(source: Dict[str, Any]) -> str:
    relative_path = normalize_path(str(source.get("relative_path", "")))
    line_start = source.get("line_start")
    line_end = source.get("line_end")

    if line_start is None:
        return relative_path

    if line_end is None or line_start == line_end:
        return f"{relative_path}:{line_start}"

    return f"{relative_path}:{line_start}-{line_end}"


def get_actual_sources(response: AgentResponse) -> List[str]:
    return [source_from_agent_source(source) for source in response.sources]


def source_matches(expected: str, actual: str) -> bool:
    """
    Flexible matching:
    - exact match passes
    - expected single line can match an actual range if line is inside range
    - expected range can match exact same actual range
    """
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

    def parse_line_range(line_text: str):
        if "-" in line_text:
            start, end = line_text.split("-", 1)
            return int(start), int(end)
        line = int(line_text)
        return line, line

    try:
        expected_start, expected_end = parse_line_range(expected_lines)
        actual_start, actual_end = parse_line_range(actual_lines)
    except ValueError:
        return False

    # expected single line inside actual range
    if expected_start == expected_end:
        return actual_start <= expected_start <= actual_end

    # expected range exactly same or covered by actual range
    return actual_start <= expected_start and expected_end <= actual_end


def evaluate_response(case: EvalCase, response: AgentResponse) -> EvalResult:
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

    exact_source_match = hit_count == len(case.expected_sources)

    return EvalResult(
        id=case.id,
        question=case.question,
        expected_query_type=case.expected_query_type,
        actual_query_type=response.query_type,
        query_type_correct=query_type_correct,
        expected_sources=case.expected_sources,
        actual_sources=actual_sources,
        source_hit_count=hit_count,
        source_recall=source_recall,
        exact_source_match=exact_source_match,
        answer=response.answer,
    )


def summarize_eval_results(results: List[EvalResult]) -> Dict[str, float]:
    if not results:
        return {
            "num_cases": 0,
            "query_type_accuracy": 0.0,
            "avg_source_recall": 0.0,
            "exact_source_match_rate": 0.0,
        }

    num_cases = len(results)

    query_type_accuracy = sum(
        1 for result in results if result.query_type_correct
    ) / num_cases

    avg_source_recall = sum(
        result.source_recall for result in results
    ) / num_cases

    exact_source_match_rate = sum(
        1 for result in results if result.exact_source_match
    ) / num_cases

    return {
        "num_cases": float(num_cases),
        "query_type_accuracy": query_type_accuracy,
        "avg_source_recall": avg_source_recall,
        "exact_source_match_rate": exact_source_match_rate,
    }