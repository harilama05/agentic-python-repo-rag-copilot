"""
Answer generator — calls the LLM (via OpenAI-compatible API) with the
constructed prompt and returns a structured answer.

Uses ``openai`` SDK which is compatible with OpenAI, Azure OpenAI,
and any OpenAI-compatible endpoint (LM Studio, Ollama, vLLM, etc.).
"""

from typing import Any, Dict, List, Optional

import openai

from src.config import settings
from src.generation.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.generation.context_builder import build_context
from src.schemas import SearchResult


class AnswerGenerator:
    """
    Generates natural-language answers from retrieved context using an LLM.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key or settings.openai_api_key or "no-key"
        self._model = model or settings.llm_model
        self._client = openai.OpenAI(
            api_key=self._api_key,
            base_url=base_url,
        )

    def generate(
        self,
        question: str,
        results: List[SearchResult],
        system_prompt: str | None = None,
        max_chunks: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate an answer from retrieved results.

        Returns a dict with ``answer``, ``token_usage``, and ``model``.
        """
        context = build_context(results, max_chunks=max_chunks)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            question=question, context=context
        )

        messages = [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

            answer = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            return {
                "answer": answer,
                "token_usage": usage,
                "model": self._model,
            }

        except openai.AuthenticationError:
            return {
                "answer": (
                    "⚠️ **LLM API key not configured.** "
                    "Please set `OPENAI_API_KEY` in your `.env` file.\n\n"
                    "Showing raw retrieved context instead:\n\n" + context
                ),
                "token_usage": {},
                "model": self._model,
            }

        except Exception as exc:
            return {
                "answer": (
                    f"⚠️ **LLM call failed:** {exc}\n\n"
                    "Showing raw retrieved context instead:\n\n" + context
                ),
                "token_usage": {},
                "model": self._model,
            }
