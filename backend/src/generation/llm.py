"""LLM client abstractions used by the application.

This package isolates model access, prompt templates, and grounded answer
generation from the rest of the agent runtime.
"""

import os
import requests
from typing import Optional
from dotenv import load_dotenv

class BaseLLM:
    """Base interface for LLM providers."""
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError()

class DeepSeekLLM(BaseLLM):
    """Wrapper around the DeepSeek API."""
    def __init__(self, model: Optional[str] = None):
        load_dotenv()
        
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is missing. Add it to your .env file "
                "or disable LLM generation in the UI."
            )
            
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = "https://api.deepseek.com/chat/completions"
        
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0
        }
        
        response = requests.post(self.base_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

# Gemini is kept as an alternative backend, selectable via LLM_BACKEND
class GeminiLLM(BaseLLM):
    """Wrapper around the Gemini API using the official Google GenAI SDK."""
    def __init__(self, model: Optional[str] = None):
        from google import genai
        from google.genai import types
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
        from google.genai import types
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
            ),
        )
        return response.text.strip()

def get_llm() -> BaseLLM:
    """Factory function to get the configured LLM backend."""
    load_dotenv()
    backend = os.getenv("LLM_BACKEND", "deepseek").lower()
    if backend == "gemini":
        return GeminiLLM()
    return DeepSeekLLM()

