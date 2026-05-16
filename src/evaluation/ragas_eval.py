"""
RAGAS evaluation integration.

Provides a wrapper to run RAGAS metrics (faithfulness, answer_relevancy,
context_precision, context_recall) on the RAG pipeline output.

Requires: ``pip install ragas datasets``
"""

from typing import Any, Dict, List, Optional


def run_ragas_evaluation(
    questions: List[str],
    answers: List[str],
    contexts: List[List[str]],
    ground_truths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run RAGAS evaluation metrics.

    Returns a dict of metric names to scores.

    Requires the ``ragas`` and ``datasets`` packages.
    """
    try:
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from datasets import Dataset

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }

        if ground_truths:
            data["ground_truth"] = ground_truths

        dataset = Dataset.from_dict(data)

        metrics = [faithfulness, answer_relevancy, context_precision]
        if ground_truths:
            metrics.append(context_recall)

        result = evaluate(dataset, metrics=metrics)
        return dict(result)

    except ImportError:
        return {
            "error": (
                "RAGAS not installed. Run: pip install ragas datasets"
            )
        }
    except Exception as exc:
        return {"error": str(exc)}
