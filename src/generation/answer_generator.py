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
from src.generation.citation_builder import build_citations
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

        Returns a dict with ``answer``, ``token_usage``, ``model``, and ``sources``.
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
            
            # Build citations from results
            citations = build_citations(results)
            
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            # Add sources section at the end
            sources_section = "\n\n---\n\n**Sources:**\n" + "\n".join(f"- {c}" for c in citations)

            return {
                "answer": answer + sources_section,
                "token_usage": usage,
                "model": self._model,
                "sources": citations,
            }

        except openai.AuthenticationError:
            citations = build_citations(results)
            sources_section = "\n\n---\n\n**Sources:**\n" + "\n".join(f"- {c}" for c in citations)
            
            return {
                "answer": (
                    "⚠️ **LLM API key not configured.** "
                    "Please set `OPENAI_API_KEY` in your `.env` file.\n\n"
                    "**Raw Code Context:**\n\n" + context + sources_section
                ),
                "token_usage": {},
                "model": self._model,
                "sources": citations,
            }

        except Exception as exc:
            citations = build_citations(results)
            sources_section = "\n\n---\n\n**Sources:**\n" + "\n".join(f"- {c}" for c in citations)
            
            return {
                "answer": (
                    f"⚠️ **LLM call failed:** {exc}\n\n"
                    "**Raw Code Context:**\n\n" + context + sources_section
                ),
                "token_usage": {},
                "model": self._model,
                "sources": citations,
            }
