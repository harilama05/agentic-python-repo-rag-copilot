"""Verify the HTTP contract and bounded conversation wiring end to end."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

from api.main import app
from src.agent_core.agent import CodebaseAgent
from src.agent_core.query_router import LLMQueryRouter
from src.services.repository_service import _store_indexed_codebase
from src.services.session_store import SessionStore
from test_agent_loop import ScriptedLLM, finish, make_tools, tool


class APISessionTests(unittest.TestCase):
    def setUp(self):
        self.store = SessionStore()
        self.client = TestClient(app)

    def bind(self, session_id, llm):
        tools = make_tools()
        indexed = SimpleNamespace(
            agent=CodebaseAgent(tools, LLMQueryRouter(), llm=llm, use_llm=True),
            tools=tools, repo_id="tasks", repo_name="Tasks", source_type="company",
            is_persistent=True, chunk_count=1,
        )
        self.store.set_indexed_codebase(session_id, indexed)
        return indexed

    def test_chat_returns_status_trace_sources_and_uses_history(self):
        llm = ScriptedLLM([tool("read_file", file_path="tasks.py"), finish(),
                           tool("find_callers", symbol_name="save_task"), finish(query_type="caller_query")])
        self.bind("session-a", llm)
        with patch("src.services.chat_service.get_default_session_store", return_value=self.store):
            first = self.client.post("/chat", json={"session_id": "session-a", "question": "Explain create_task"})
            second = self.client.post("/chat", json={"session_id": "session-a", "question": "Who calls that function?"})
        self.assertEqual(first.status_code, 200)
        payload = first.json()
        self.assertEqual(payload["status"], "completed")
        self.assertIn("steps", payload["raw_results"])
        self.assertEqual(payload["sources"][0]["relative_path"], "tasks.py")
        self.assertEqual(second.json()["raw_results"]["history_turns"], 1)

    def test_unloaded_or_empty_question_is_not_sent_to_model(self):
        with patch("src.services.chat_service.get_default_session_store", return_value=self.store):
            self.assertEqual(self.client.post("/chat", json={"session_id": "missing", "question": "Explain"}).status_code, 400)
            self.assertEqual(self.client.post("/chat", json={"session_id": "missing", "question": " "}).status_code, 400)

    def test_switching_repository_clears_history(self):
        indexed = self.bind("session-a", ScriptedLLM([]))
        self.store.get_or_create_session("session-a").chat_history = [SimpleNamespace(question="old repo", answer="old answer")]
        _store_indexed_codebase(session_id="session-a", session_store=self.store, indexed=indexed)
        self.assertEqual(self.store.get_chat_history("session-a"), [])

    def test_history_is_bounded_and_isolated_between_sessions(self):
        for index in range(9):
            self.store.append_chat_response("session-a", SimpleNamespace(question=str(index), answer="answer"))
        self.assertEqual(len(self.store.get_chat_history("session-a")), 4)
        self.assertEqual(self.store.get_chat_history("session-b"), [])

    def test_health_does_not_need_external_services(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
