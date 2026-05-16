"""
Usage tracker — records query counts, token usage, and latency.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone

from src.config import settings


class UsageTracker:
    """Simple file-backed usage tracker."""

    def __init__(self, log_dir: Path | None = None):
        self._log_dir = log_dir or settings.logs_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "usage.jsonl"

    def log_query(
        self,
        question: str,
        query_type: str,
        tools_used: List[str],
        token_usage: Dict[str, int],
        latency_ms: float = 0.0,
    ) -> None:
        """Append a query log entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "query_type": query_type,
            "tools_used": tools_used,
            "token_usage": token_usage,
            "latency_ms": round(latency_ms, 2),
        }

        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_stats(self) -> Dict[str, Any]:
        """Read all logs and compute summary stats."""
        if not self._log_file.exists():
            return {"total_queries": 0}

        entries = []
        for line in self._log_file.read_text("utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        total_tokens = sum(
            e.get("token_usage", {}).get("total_tokens", 0) for e in entries
        )

        return {
            "total_queries": len(entries),
            "total_tokens": total_tokens,
            "avg_latency_ms": (
                sum(e.get("latency_ms", 0) for e in entries) / len(entries)
                if entries
                else 0
            ),
        }
