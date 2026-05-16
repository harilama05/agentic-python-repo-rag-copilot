"""
Evaluation runner — runs a batch of eval cases through the agent
and computes metrics.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.schemas import EvalCase, EvalResult
from src.agent.graph import AgentGraph
from src.evaluation.metrics import compute_metrics
from src.generation.context_builder import build_context


class EvalRunner:
    """
    Runs evaluation test cases against an ``AgentGraph``.
    """

    def __init__(self, agent: AgentGraph):
        self.agent = agent

    def load_cases(self, path: str | Path) -> List[EvalCase]:
        """Load eval cases from a JSON file."""
        data = json.loads(Path(path).read_text("utf-8"))
        return [EvalCase(**item) for item in data]

    def run(self, cases: List[EvalCase]) -> List[EvalResult]:
        """Run all eval cases and compute metrics."""
        results: List[EvalResult] = []

        for case in cases:
            response = self.agent.invoke(case.question)

            retrieved_sources = [
                s.get("relative_path", "") for s in response.sources
            ]

            # Build context for faithfulness check
            context = response.answer  # simplified

            metrics = compute_metrics(
                question=case.question,
                answer=response.answer,
                context=context,
                expected_sources=case.expected_sources,
                retrieved_sources=retrieved_sources,
            )

            results.append(
                EvalResult(
                    question=case.question,
                    generated_answer=response.answer,
                    expected_answer=case.expected_answer,
                    sources_retrieved=retrieved_sources,
                    metrics=metrics,
                )
            )

        return results

    def run_and_save(
        self,
        cases: List[EvalCase],
        output_path: str | Path,
    ) -> List[EvalResult]:
        """Run evaluation and save results to JSON."""
        results = self.run(cases)

        output = [r.model_dump() for r in results]
        Path(output_path).write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return results
