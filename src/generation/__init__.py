"""Canonical generation package for LLM answer construction.

This package isolates model access, prompt templates, and grounded answer
generation from the rest of the agent runtime.
"""

from src.generation.answer_generator import GroundedAnswerGenerator
from src.generation.llm import GeminiLLM

__all__ = ["GeminiLLM", "GroundedAnswerGenerator"]
