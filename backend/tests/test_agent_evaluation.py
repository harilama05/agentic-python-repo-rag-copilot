"""Record agent completion and work budgets alongside answer quality metrics."""

import unittest

from src.agent_core.response_models import AgentResponse
from src.evaluation.eval_runner import EvalCase, evaluate_response, summarize_eval_results


class AgentEvaluationTests(unittest.TestCase):
    def test_failed_run_is_not_reported_as_completed(self):
        case = EvalCase("one", "repo", ".", "Explain", "search_query", [])
        response = AgentResponse("Explain", "search_query", "Could not finish", [], [], {
            "tool_call_count": 3, "model_steps": 2, "usage": {"total_tokens": 100},
        }, status="budget_exhausted")
        result = evaluate_response(case, response)
        summary = summarize_eval_results([result])
        self.assertEqual(summary["agent_completion_rate"], 0)
        self.assertEqual(summary["avg_tool_call_count"], 3)
        self.assertEqual(summary["avg_model_steps"], 2)
        self.assertEqual(summary["avg_total_tokens"], 100)

    def test_empty_summary_keeps_agent_metric_keys(self):
        self.assertEqual(summarize_eval_results([])["agent_completion_rate"], 0)


if __name__ == "__main__":
    unittest.main()
