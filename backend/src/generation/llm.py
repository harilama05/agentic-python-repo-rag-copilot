"""OpenAI Responses API adapter for the repository agent."""

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass
class LLMTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    content: Any = None
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""


class BaseLLM:
    supports_tools = False

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def chat(self, *, system_prompt: str, messages: list[Any],
             tools: list[dict], timeout_seconds: float) -> LLMTurn:
        raise NotImplementedError

    def tool_results_message(self, results: list[tuple[ToolCall, dict]]) -> Any:
        raise NotImplementedError


class OpenAILLM(BaseLLM):
    """Explicit function calling; the application owns the loop and its budgets.

    Preserve all Responses output items, including encrypted reasoning, when
    continuing a tool turn. Conversation state belongs to each run.
    """

    supports_tools = True

    def __init__(self, model: str | None = None, *, client: httpx.Client | None = None):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key or self.api_key in {"your_openai_api_key_here", "PASTE_YOUR_OPENAI_KEY_HERE"}:
            raise ValueError("OPENAI_API_KEY is missing. Paste your key into backend/.env.")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-6-luna").strip()
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "low").strip()
        if self.reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("Invalid OPENAI_REASONING_EFFORT.")
        self.client = client or httpx.Client(base_url="https://api.openai.com/v1/")

    @staticmethod
    def _input_items(messages: list[Any]) -> list[dict]:
        items = []
        for message in messages:
            # A model turn and its function results can each contain many items.
            for item in message if isinstance(message, list) else [message]:
                if not isinstance(item, dict):
                    raise ValueError("Responses messages must be dictionaries.")
                if "role" in item and "text" in item:
                    items.append({"role": item["role"], "content": item["text"]})
                else:
                    items.append(item)
        return items

    def chat(self, *, system_prompt: str, messages: list[Any],
             tools: list[dict], timeout_seconds: float = 60) -> LLMTurn:
        if timeout_seconds <= 0:
            raise ValueError("Model call timeout must be positive.")
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": self._input_items(messages),
            "max_output_tokens": 4096,
            "reasoning": {"effort": self.reasoning_effort},
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if tools:
            payload["tools"] = [
                {"type": "function", **declaration, "strict": False}
                for declaration in tools
            ]
            payload["tool_choice"] = "auto"
            # Finish must observe previous tools, so request one action per turn.
            payload["parallel_tool_calls"] = False
        response = self.client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "completed":
            raise RuntimeError("OpenAI returned a non-completed response.")
        output = data.get("output") or []
        calls = []
        texts = []
        for item in output:
            if item.get("type") == "function_call":
                arguments = json.loads(item["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")
                calls.append(ToolCall(item["name"], arguments, item["call_id"]))
            elif item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        texts.append(part["text"])
        if not calls and not texts:
            raise RuntimeError("OpenAI returned no usable text or function calls.")
        usage = data.get("usage") or {}
        return LLMTurn(
            text="\n".join(texts).strip(), tool_calls=calls, content=output,
            usage={name: int(usage.get(name) or 0)
                   for name in ("input_tokens", "output_tokens", "total_tokens")},
            finish_reason=data["status"],
        )

    def tool_results_message(self, results: list[tuple[ToolCall, dict]]) -> list[dict]:
        items = []
        for call, result in results:
            if not call.call_id:
                raise ValueError("OpenAI function result requires a call_id.")
            items.append({"type": "function_call_output", "call_id": call.call_id,
                          "output": json.dumps(result, ensure_ascii=False)})
        return items

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        turn = self.chat(system_prompt=system_prompt,
                         messages=[{"role": "user", "text": user_prompt}],
                         tools=[], timeout_seconds=60)
        if not turn.text:
            raise RuntimeError("OpenAI returned an empty text response.")
        return turn.text


def get_llm() -> BaseLLM:
    load_dotenv()
    backend = os.getenv("LLM_BACKEND", "openai").strip().lower()
    if backend != "openai":
        raise ValueError("Set LLM_BACKEND=openai to use the OpenAI provider.")
    return OpenAILLM()

