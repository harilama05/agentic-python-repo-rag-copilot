"""
Test set builder — generates evaluation test cases from an indexed codebase.
"""

import json
import random
from pathlib import Path
from typing import List

from src.schemas import EvalCase
from src.storage.metadata_store import MetadataStore


def build_testset(
    metadata_store: MetadataStore,
    num_cases: int = 20,
    output_path: str | Path | None = None,
) -> List[EvalCase]:
    """
    Auto-generate eval cases from indexed metadata.

    Creates questions like:
    - "Where is X defined?"
    - "What does X do?"
    - "Where is X used?"
    """
    all_meta = list(metadata_store._data.values())

    # Filter to symbols with names
    symbols = [m for m in all_meta if m.get("symbol_name")]

    if not symbols:
        return []

    random.shuffle(symbols)
    symbols = symbols[:num_cases]

    templates = [
        ("Where is {name} defined?", "location"),
        ("What does {name} do?", "explanation"),
        ("Where is {name} used?", "reference"),
        ("Find code related to {name}", "search"),
    ]

    cases: List[EvalCase] = []

    for meta in symbols:
        name = meta["symbol_name"]
        rel_path = meta.get("relative_path", "")
        template, tag = random.choice(templates)

        cases.append(
            EvalCase(
                question=template.format(name=name),
                expected_answer=f"{name} is defined in {rel_path}",
                expected_sources=[rel_path],
                tags=[tag, meta.get("symbol_type", "")],
            )
        )

    if output_path:
        Path(output_path).write_text(
            json.dumps([c.model_dump() for c in cases], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return cases
