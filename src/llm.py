import os
from typing import Optional

from dotenv import load_dotenv
from google import genai


class GeminiLLM:
    """
    Wrapper around Gemini API using the official Google GenAI SDK.
    Used for grounded natural-language answer generation.
    """

    def __init__(self, model: Optional[str] = None):
        load_dotenv()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing. Add it to your .env file "
                "or disable LLM generation in the UI."
            )

        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        full_prompt = f"""
{system_prompt}

{user_prompt}
"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
        )

        return response.text.strip()