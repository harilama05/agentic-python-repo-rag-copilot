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

    expected_keys = {source_key(source) for source in expected_sources}
    actual_keys = [source_key(source) for source in actual_sources]

    hits = sum(1 for key in actual_keys if key in expected_keys)

    return hits / len(actual_keys)


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