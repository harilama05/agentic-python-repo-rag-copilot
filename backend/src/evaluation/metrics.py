"""Extended evaluation metrics for repository QA behavior.

This module adds lightweight metrics on top of the existing eval runner:
- latency
- source precision
- citation validity
- answer non-empty rate
- router fallback rate
- LLM failure rate

The functions are defensive because eval cases and response sources may be
represented as strings, dictionaries, or small dataclass-like objects.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any


_SOURCE_RE = re.compile(
    r"^(?P<path>.*?):(?P<start>\d+)(?:-(?P<end>\d+))?$"
)

_ABSTENTION_PATTERNS = [
    "không thấy",
    "chưa thấy",
    "không tìm thấy",
    "không có bằng chứng",
    "không đủ thông tin",
    "không có thông tin",
    "không xác định được",
    "not found",
    "no evidence",
    "not enough information",
    "cannot determine",
    "could not find",
]


def now_seconds() -> float:
    """Return a monotonic timestamp for latency measurement."""
    return time.perf_counter()


def compute_latency_seconds(start_time: float, end_time: float) -> float:
    """Compute elapsed time in seconds."""
    return max(0.0, end_time - start_time)


def _get_value(item: Any, key: str, default: Any = None) -> Any:
    """Read a value from dict-like or object-like data."""
    if isinstance(item, dict):
        return item.get(key, default)

    return getattr(item, key, default)


def normalize_source(source: Any) -> dict[str, Any]:
    """Normalize a source into a standard dictionary.

    Supported inputs:
    - "app/main.py:5"
    - "app/main.py:1-5"
    - {"relative_path": "...", "line_start": 1, "line_end": 5}
    - dataclass/object with similar attributes
    """
    if isinstance(source, str):
        match = _SOURCE_RE.match(source.strip())

        if not match:
            return {
                "relative_path": source.strip().replace("\\", "/"),
                "line_start": None,
                "line_end": None,
            }

        relative_path = match.group("path").replace("\\", "/")
        line_start = int(match.group("start"))
        line_end = int(match.group("end") or line_start)

        return {
            "relative_path": relative_path,
            "line_start": line_start,
            "line_end": line_end,
        }

    relative_path = (
        _get_value(source, "relative_path")
        or _get_value(source, "file_path")
        or ""
    )

    line_start = (
        _get_value(source, "line_start")
        or _get_value(source, "start_line")
        or _get_value(source, "line_number")
    )

    line_end = (
        _get_value(source, "line_end")
        or _get_value(source, "end_line")
        or line_start
    )

    try:
        line_start = int(line_start) if line_start is not None else None
    except (TypeError, ValueError):
        line_start = None

    try:
        line_end = int(line_end) if line_end is not None else line_start
    except (TypeError, ValueError):
        line_end = line_start

    return {
        "relative_path": str(relative_path).replace("\\", "/"),
        "line_start": line_start,
        "line_end": line_end,
    }


def source_key(source: Any) -> tuple[str, int | None, int | None]:
    """Return a comparable key for a source."""
    normalized = normalize_source(source)

    return (
        normalized["relative_path"],
        normalized["line_start"],
        normalized["line_end"],
    )


def source_path(source: Any) -> str:
    """Return the normalized relative file path for a source."""
    return normalize_source(source)["relative_path"]


def source_matches(expected: Any, actual: Any) -> bool:
    """Return True when an actual source satisfies an expected source.

    A ranged actual source matches when it fully covers the expected range.
    If either side only has a file path, matching falls back to path equality.
    """
    expected_normalized = normalize_source(expected)
    actual_normalized = normalize_source(actual)

    expected_path = expected_normalized["relative_path"]
    actual_path = actual_normalized["relative_path"]

    if not expected_path or expected_path != actual_path:
        return False

    expected_start = expected_normalized["line_start"]
    expected_end = expected_normalized["line_end"]
    actual_start = actual_normalized["line_start"]
    actual_end = actual_normalized["line_end"]

    if (
        expected_start is None
        or expected_end is None
        or actual_start is None
        or actual_end is None
    ):
        return True

    return actual_start <= expected_start and expected_end <= actual_end


def compute_source_precision(
    actual_sources: list[Any],
    expected_sources: list[Any],
) -> float:
    """Compute source precision.

    Precision = matched actual sources / actual sources.

    If there are no actual sources, precision is 0.0.
    """
    if not actual_sources:
        return 0.0

    hits = sum(
        1
        for actual_source in actual_sources
        if any(
            source_matches(expected_source, actual_source)
            for expected_source in expected_sources
        )
    )

    return hits / len(actual_sources)


def compute_file_hit_rate(
    actual_sources: list[Any],
    expected_files: list[str],
) -> float:
    """Compute how many expected files appear in actual sources."""
    if not expected_files:
        return 1.0

    actual_paths = {source_path(source) for source in actual_sources}
    expected_paths = {
        str(file_path).replace("\\", "/").strip()
        for file_path in expected_files
    }
    hits = sum(1 for expected_path in expected_paths if expected_path in actual_paths)

    return hits / len(expected_paths)


def compute_keyword_recall(
    answer: str | None,
    expected_keywords: list[str],
) -> float:
    """Compute expected keyword recall for an answer."""
    if not expected_keywords:
        return 1.0

    normalized_answer = (answer or "").lower()
    normalized_keywords = [keyword.lower() for keyword in expected_keywords]
    hits = sum(1 for keyword in normalized_keywords if keyword in normalized_answer)

    return hits / len(normalized_keywords)


def has_forbidden_keywords(
    answer: str | None,
    forbidden_keywords: list[str],
) -> bool:
    """Return True when an answer contains forbidden keywords."""
    if not forbidden_keywords:
        return False

    normalized_answer = (answer or "").lower()

    return any(
        keyword.lower() in normalized_answer
        for keyword in forbidden_keywords
    )


def is_abstaining(answer: str | None) -> bool:
    """Return True when an answer appears to refuse due to missing evidence."""
    normalized_answer = (answer or "").lower()

    return any(pattern in normalized_answer for pattern in _ABSTENTION_PATTERNS)


def compute_abstention_correct(
    answer: str | None,
    requires_abstention: bool,
) -> bool | None:
    """Compute abstention correctness when the case requires abstention."""
    if not requires_abstention:
        return None

    return is_abstaining(answer)


def validate_citations(
    repo_root: str | Path,
    sources: list[Any],
) -> dict[str, Any]:
    """Validate source citations.

    A valid citation must:
    - include relative_path
    - include line_start/line_end
    - point to an existing file
    - have a valid line range inside the file
    """
    root = Path(repo_root).resolve()

    total = len(sources)
    valid = 0
    invalid_items: list[dict[str, Any]] = []

    for source in sources:
        normalized = normalize_source(source)

        relative_path = normalized["relative_path"]
        line_start = normalized["line_start"]
        line_end = normalized["line_end"]

        if not relative_path or line_start is None or line_end is None:
            invalid_items.append(
                {
                    "source": source,
                    "reason": "missing relative_path or line range",
                }
            )
            continue

        file_path = (root / relative_path).resolve()

        if not file_path.exists():
            invalid_items.append(
                {
                    "source": source,
                    "reason": "file does not exist",
                }
            )
            continue

        try:
            total_lines = len(
                file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines()
            )
        except Exception as exc:
            invalid_items.append(
                {
                    "source": source,
                    "reason": f"could not read file: {exc}",
                }
            )
            continue

        if line_start < 1 or line_end < line_start:
            invalid_items.append(
                {
                    "source": source,
                    "reason": "invalid line range",
                }
            )
            continue

        if line_end > total_lines:
            invalid_items.append(
                {
                    "source": source,
                    "reason": "line range exceeds file length",
                }
            )
            continue

        valid += 1

    citation_validity_rate = 1.0 if total == 0 else valid / total

    return {
        "citation_count": total,
        "valid_citation_count": valid,
        "citation_validity_rate": citation_validity_rate,
        "invalid_citations": invalid_items,
    }


def answer_non_empty(answer: str | None) -> bool:
    """Return True if an answer is non-empty."""
    return bool(answer and answer.strip())


def extract_router_name(raw_results: dict[str, Any] | None) -> str | None:
    """Extract router name from raw_results."""
    if not raw_results:
        return None

    router = raw_results.get("router")

    if router:
        return router

    query_plan = raw_results.get("query_plan")

    if isinstance(query_plan, dict):
        return query_plan.get("router")

    return None


def is_router_fallback(raw_results: dict[str, Any] | None) -> bool:
    """Return True if fallback rule-based router was used."""
    return extract_router_name(raw_results) == "fallback_rule"


def is_llm_failure(raw_results: dict[str, Any] | None) -> bool:
    """Return True if raw_results indicates LLM answer generation failure."""
    if not raw_results:
        return False

    return raw_results.get("llm_enabled") is False and bool(
        raw_results.get("llm_error")
    )


def safe_average(values: list[float]) -> float:
    """Return average for a list of floats."""
    if not values:
        return 0.0

    return sum(values) / len(values)
