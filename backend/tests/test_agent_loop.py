"""Exercise the actual loop/tool boundary without API keys, models or databases."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.agent_core.agent import CodebaseAgent
from src.agent_core.agent_loop import AgentLimits, AgentLoop
from src.agent_core.query_router import LLMQueryRouter
from src.agent_core.tool_registry import ToolRegistry
from src.agent_core.tools import CodebaseTools
from src.generation.llm import BaseLLM, LLMTurn, ToolCall
from src.graph.code_graph import CodeGraph, CodeNode


SOURCE = "LIMIT = 10\n\ndef create_task():\n    return save_task()\n\ndef save_task():\n    return LIMIT\n"


def make_tools():
    graph = CodeGraph()
    graph.add_node(CodeNode("create", "create_task", "create_task", "function", "tasks.py", 3, 4))
    graph.add_node(CodeNode("save", "save_task", "save_task", "function", "tasks.py", 6, 7))
    graph.add_edge("create", "save", "calls")
    chunks = [{"text": "def create_task():\n    return save_task()", "metadata": {
        "relative_path": "tasks.py", "start_line": 3, "end_line": 4,
        "symbol_name": "create_task", "qualified_name": "create_task", "symbol_type": "function",
    }}]
    return CodebaseTools(SimpleNamespace(indexed_chunks=chunks), ".", code_graph=graph,
                         source_files={"tasks.py": SOURCE})


def tool(name, **args):
    return LLMTurn(tool_calls=[ToolCall(name, args)], content={"role": "assistant", "text": "tool call"})


def finish(answer="create_task calls save_task.", source_ids=None, **kwargs):
    return tool("finish_answer", answer=answer, source_ids=source_ids if source_ids is not None else ["S1"],
                query_type=kwargs.pop("query_type", "explanation_query"),
                status=kwargs.pop("status", "completed"), **kwargs)


class ScriptedLLM(BaseLLM):
    supports_tools = True

    def __init__(self, turns):
        self.turns = iter(turns)
        self.requests = []

    def chat(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        turn = next(self.turns)
        if isinstance(turn, Exception):
            raise turn
        return turn

    def tool_results_message(self, results):
        return {"role": "user", "text": str([(call.name, result) for call, result in results]),
                "results": [result for _, result in results]}


class AgentLoopTests(unittest.TestCase):
    def run_loop(self, turns, **limits):
        llm = ScriptedLLM(turns)
        response = AgentLoop(make_tools(), llm, AgentLimits(**limits)).run("Explain create_task")
        return response, llm

    def test_next_action_observes_previous_tool_result(self):
        response, llm = self.run_loop([
            tool("find_callees", symbol_name="create_task"),
            tool("read_file", file_path="tasks.py", start_line=6, end_line=7),
            finish(source_ids=["S2"]),
        ])
        self.assertEqual(response.status, "completed")
        self.assertIn("save_task", llm.requests[1]["messages"][-1]["text"])
        self.assertEqual(response.sources[0]["line_start"], 6)
        self.assertEqual(response.raw_results["model_steps"], 3)

    def test_unknown_tool_error_is_observed_then_recovered(self):
        response, llm = self.run_loop([
            tool("run_shell", command="anything"),
            tool("read_file", file_path="tasks.py"), finish(),
        ])
        self.assertFalse(llm.requests[1]["messages"][-1]["results"][0]["ok"])
        self.assertEqual(response.status, "completed")

    def test_invalid_arguments_are_not_executed(self):
        response, llm = self.run_loop([
            tool("read_file", file_path="tasks.py", start_line=-1),
            tool("read_file", file_path="tasks.py", start_line=1), finish(),
        ])
        self.assertIn("error", llm.requests[1]["messages"][-1]["results"][0])
        self.assertEqual(response.status, "completed")

    def test_fabricated_evidence_id_rejected(self):
        response, llm = self.run_loop([
            finish(source_ids=["S999"]),
            finish(answer="Insufficient evidence.", source_ids=[], status="insufficient_evidence"),
        ])
        self.assertEqual(response.status, "insufficient_evidence")
        self.assertEqual(response.sources, [])
        self.assertIn("Unknown evidence", llm.requests[1]["messages"][-1]["text"])

    def test_completion_without_evidence_rejected(self):
        response, _ = self.run_loop([finish(source_ids=[])] * 3)
        self.assertEqual(response.status, "stalled")

    def test_plain_hallucinated_text_is_not_accepted(self):
        response, _ = self.run_loop([LLMTurn(text="There is a secret_function.")] * 2, max_steps=2)
        self.assertEqual(response.status, "budget_exhausted")
        self.assertNotIn("secret_function", response.answer)

    def test_step_and_call_budgets(self):
        response, _ = self.run_loop([tool("read_file", file_path="tasks.py")], max_steps=1)
        self.assertEqual(response.raw_results["stop_reason"], "max_steps")
        response, _ = self.run_loop([
            tool("read_file", file_path="tasks.py"), finish(),
        ], max_tool_calls=1)
        self.assertEqual(response.raw_results["stop_reason"], "max_tool_calls")

    def test_context_budget_stops_before_calling_model(self):
        response, llm = self.run_loop([], max_context_chars=1)
        self.assertEqual(response.raw_results["stop_reason"], "context_limit")
        self.assertEqual(llm.requests, [])

    def test_deadline_stops_before_calling_model(self):
        with patch("src.agent_core.agent_loop.time.monotonic", side_effect=[0, 100, 100]):
            response, llm = self.run_loop([], timeout_seconds=1)
        self.assertEqual(response.raw_results["stop_reason"], "timeout")
        self.assertEqual(llm.requests, [])

    def test_repeated_actions_are_cached_and_then_stopped(self):
        llm = ScriptedLLM([tool("read_file", file_path="tasks.py")] * 3)
        tools = make_tools()
        with patch.object(tools, "read_file", wraps=tools.read_file) as read:
            response = AgentLoop(tools, llm).run("Explain create_task")
        self.assertEqual(response.status, "stalled")
        # One execution, plus one excerpt read during evidence registration.
        self.assertEqual(read.call_count, 2)

    def test_api_error_does_not_leak_exception_details(self):
        response, _ = self.run_loop([RuntimeError("credential=SECRET")])
        self.assertEqual(response.status, "model_error")
        self.assertNotIn("SECRET", str(response))

    def test_evidence_does_not_leak_between_runs(self):
        llm = ScriptedLLM([tool("read_file", file_path="tasks.py"), finish(),
                           finish(source_ids=["S1"]),
                           finish(source_ids=[], status="insufficient_evidence")])
        loop = AgentLoop(make_tools(), llm)
        self.assertEqual(loop.run("First").status, "completed")
        self.assertEqual(loop.run("Second").sources, [])

    def test_zero_count_is_valid_evidence(self):
        response, _ = self.run_loop([
            tool("count_symbols", symbol_type="class"),
            finish(answer="There are no indexed classes.", source_ids=[], query_type="count_query"),
        ])
        self.assertEqual(response.status, "completed")

    def test_native_agent_path_does_not_call_old_router(self):
        router = LLMQueryRouter()
        llm = ScriptedLLM([tool("read_file", file_path="tasks.py"), finish()])
        agent = CodebaseAgent(make_tools(), router, llm=llm, use_llm=True)
        with patch.object(router, "route_many", side_effect=AssertionError("old planner called")):
            response = agent.answer("What does it do?", history=[{"question": "Find create_task", "answer": "create_task"}])
        self.assertEqual(response.raw_results["history_turns"], 1)
        self.assertEqual(llm.requests[0]["messages"][0]["text"], "Find create_task")

    def test_static_flow_uses_graph_edges(self):
        response, _ = self.run_loop([tool("trace_flow", symbol_name="create_task"),
                                     finish(query_type="flow_query")])
        self.assertEqual(response.query_type, "flow_query")
        self.assertIn("trace_flow", response.tools_used[0])

    def test_read_file_cannot_access_nonindexed_paths(self):
        registry = ToolRegistry(make_tools())
        with self.assertRaises(FileNotFoundError):
            registry.execute("read_file", {"file_path": "../.env"})
        with self.assertRaises(ValueError):
            registry.execute("read_file", {"file_path": "tasks.py", "unexpected": True})

    def test_missing_file_snapshot_warns_about_reindex(self):
        tools = make_tools()
        tools.source_files = None
        llm = ScriptedLLM([finish(source_ids=[], status="insufficient_evidence")])
        response = AgentLoop(tools, llm).run("Explain")
        self.assertIn("Re-index", response.warnings[0])

    def test_ambiguous_symbol_requires_disambiguation(self):
        tools = make_tools()
        tools.source_files["other.py"] = SOURCE
        tools.code_graph.add_node(CodeNode("other-create", "create_task", "create_task", "function", "other.py", 3, 4))
        self.assertTrue(tools.find_callers("create_task")["ambiguous"])
        result = tools.find_callers("tasks.py::create_task")
        self.assertFalse(result["ambiguous"])
        self.assertEqual(len(result["targets"]), 1)
        self.assertEqual(result["targets"][0]["relative_path"], "tasks.py")

    def test_multiple_calls_share_one_observation_turn(self):
        first = LLMTurn(tool_calls=[ToolCall("read_file", {"file_path": "tasks.py", "start_line": 3, "end_line": 4}),
                                    ToolCall("find_callees", {"symbol_name": "create_task"})])
        response, llm = self.run_loop([first, finish()])
        self.assertEqual(response.status, "completed")
        self.assertEqual(len(llm.requests[1]["messages"][-1]["results"]), 2)

    def test_read_results_are_bounded_and_excess_evidence_is_not_accepted(self):
        tools = make_tools()
        tools.source_files["long.py"] = "\n".join(f"VALUE_{i} = {i}" for i in range(200))
        registry = ToolRegistry(tools)
        result = registry.execute("read_file", {"file_path": "long.py", "start_line": 1, "end_line": 200})
        self.assertEqual(result["data"]["end_line"], 80)
        with self.assertRaises(ValueError):
            registry.finish({"answer": "unsupported", "source_ids": [], "query_type": "search_query"})

    def test_model_response_arriving_after_deadline_is_not_accepted(self):
        with patch("src.agent_core.agent_loop.time.monotonic", side_effect=[0, 0, 5, 5]):
            response, _ = self.run_loop([finish(source_ids=[], status="insufficient_evidence")], timeout_seconds=1)
        self.assertEqual(response.raw_results["stop_reason"], "timeout")

    def test_result_encoding_failure_returns_controlled_status(self):
        llm = ScriptedLLM([tool("read_file", file_path="tasks.py")])
        with patch.object(llm, "tool_results_message", side_effect=RuntimeError("SECRET")):
            response = AgentLoop(make_tools(), llm).run("Explain")
        self.assertEqual(response.status, "model_error")
        self.assertNotIn("SECRET", str(response))


if __name__ == "__main__":
    unittest.main()
