"""Validate OpenAI Responses HTTP payloads without an API key or network calls."""

import json
import os
import unittest
from unittest.mock import patch

import httpx

from src.agent_core.agent_loop import AgentLoop
from src.agent_core.tool_registry import ToolRegistry
from src.generation.llm import OpenAILLM, ToolCall, get_llm
from test_agent_loop import make_tools


def response(output, **extra):
    return {"id": "resp_test", "object": "response", "status": "completed", "output": output,
            "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13}, **extra}


def text_item(text):
    return {"id": "msg_test", "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": text}]}


def call_item(name="read_file", arguments=None, call_id="call_1"):
    return {"id": "fc_test", "type": "function_call", "call_id": call_id,
            "name": name, "arguments": json.dumps(arguments or {"file_path": "tasks.py"})}


class OpenAIAdapterTests(unittest.TestCase):
    def make_client(self, handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        with patch("src.generation.llm.load_dotenv"), patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "gpt-6-luna",
            "OPENAI_REASONING_EFFORT": "low",
        }):
            return OpenAILLM(client=client)

    def test_default_provider_and_model_are_openai_luna(self):
        with patch("src.generation.llm.load_dotenv"), patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            llm = get_llm()
        self.addCleanup(llm.client.close)
        self.assertIsInstance(llm, OpenAILLM)
        self.assertEqual(llm.model, "gpt-6-luna")

    def test_missing_key_gives_exact_edit_location(self):
        with patch("src.generation.llm.load_dotenv"), patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "backend/.env"):
                OpenAILLM()

    def test_payload_and_reasoning_survive_tool_round_trip(self):
        requests = []
        reasoning = {"id": "rs_test", "type": "reasoning", "summary": [], "encrypted_content": "opaque"}

        def handler(request):
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            self.assertEqual(request.extensions["timeout"]["read"], 5)
            body = json.loads(request.content)
            requests.append(body)
            output = [reasoning, call_item()] if len(requests) == 1 else [text_item("Done")]
            return httpx.Response(200, json=response(output))

        llm = self.make_client(handler)
        declarations = ToolRegistry(make_tools()).declarations()
        messages = [{"role": "user", "text": "Explain"}]
        first = llm.chat(system_prompt="investigate", messages=messages, tools=declarations, timeout_seconds=5)
        messages.extend([first.content, llm.tool_results_message([(first.tool_calls[0], {"ok": True})])])
        second = llm.chat(system_prompt="investigate", messages=messages, tools=declarations, timeout_seconds=5)
        self.assertEqual(second.text, "Done")
        self.assertEqual(first.usage["total_tokens"], 13)
        self.assertEqual(requests[0]["model"], "gpt-6-luna")
        self.assertFalse(requests[0]["store"])
        self.assertEqual(requests[0]["reasoning"], {"effort": "low"})
        self.assertNotIn("temperature", requests[0])
        self.assertEqual(len(requests[0]["tools"]), 11)
        self.assertTrue(all(tool["type"] == "function" and tool["strict"] is False for tool in requests[0]["tools"]))
        self.assertFalse(requests[0]["parallel_tool_calls"])
        self.assertEqual(requests[1]["input"][1], reasoning)
        self.assertEqual(requests[1]["input"][3]["type"], "function_call_output")
        self.assertEqual(requests[1]["input"][3]["call_id"], "call_1")

    def test_adapter_drives_real_agent_loop(self):
        requests = []

        def handler(request):
            body = json.loads(request.content)
            requests.append(body)
            output = [call_item()] if len(requests) == 1 else [call_item("finish_answer", {
                "answer": "create_task calls save_task.", "source_ids": ["S1"],
                "query_type": "explanation_query", "status": "completed",
            }, "call_final")]
            return httpx.Response(200, json=response(output))

        result = AgentLoop(make_tools(), self.make_client(handler)).run("Explain create_task")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.sources[0]["relative_path"], "tasks.py")
        self.assertIn("LIMIT", json.loads(requests[1]["input"][-1]["output"])["data"]["content"])
        self.assertEqual(result.raw_results["usage"]["total_tokens"], 26)

    def test_incomplete_response_is_not_accepted(self):
        llm = self.make_client(lambda request: httpx.Response(200, json=response([text_item("partial")], status="incomplete")))
        with self.assertRaisesRegex(RuntimeError, "non-completed"):
            llm.generate("system", "question")

    def test_empty_or_refused_output_is_not_a_successful_text_answer(self):
        llm = self.make_client(lambda request: httpx.Response(200, json=response([])))
        with self.assertRaises(RuntimeError):
            llm.generate("system", "question")

    def test_invalid_tool_arguments_are_rejected(self):
        item = call_item()
        item["arguments"] = "[]"
        llm = self.make_client(lambda request: httpx.Response(200, json=response([item])))
        with self.assertRaises(ValueError):
            llm.generate("system", "question")

    def test_http_failures_do_not_retry(self):
        attempts = []

        def handler(request):
            attempts.append(request)
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})

        llm = self.make_client(handler)
        with self.assertRaises(httpx.HTTPStatusError):
            llm.generate("system", "question")
        self.assertEqual(len(attempts), 1)

    def test_each_parallel_tool_result_has_its_own_call_id(self):
        llm = self.make_client(lambda request: httpx.Response(200, json=response([])))
        results = llm.tool_results_message([(ToolCall("read_file", {}, "one"), {"ok": True}),
                                            (ToolCall("count_files", {}, "two"), {"ok": True})])
        self.assertEqual([item["call_id"] for item in results], ["one", "two"])
        with self.assertRaises(ValueError):
            llm.tool_results_message([(ToolCall("read_file", {}), {"ok": True})])


if __name__ == "__main__":
    unittest.main()
