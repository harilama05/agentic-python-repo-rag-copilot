"""Grounded answer generation built on top of retrieval outputs.

This module preserves the app's current fallback behavior while making the LLM
answering step reusable from the agent and future API services.
"""

from src.generation.context_builder import build_generation_context
from src.generation.llm import GeminiLLM
from src.generation.prompts import SYSTEM_PROMPT, build_grounded_user_prompt


class GroundedAnswerGenerator:
    """Generate grounded answers from agent results using an LLM."""

    def __init__(self, llm: GeminiLLM):
        self.llm = llm

    def generate(
        self,
        *,
        question: str,
        query_type: str,
        tools_used: list[str],
        raw_results: dict,
    ) -> str:
        """Generate a grounded natural-language answer from agent context."""
        context = build_generation_context(
            question=question,
            query_type=query_type,
            tools_used=tools_used,
            raw_results=raw_results,
        )

        user_prompt = build_grounded_user_prompt(
            question=context["question"],
            query_type=context["query_type"],
            tools_used=context["tools_used"],
            raw_results=context["raw_results"],
        )

        return self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
