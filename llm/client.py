from __future__ import annotations
from abc import ABC, abstractmethod
import httpx


class LLMClient(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class StaticLLMClient(LLMClient):
    """Useful for unit tests; returns a predefined JSON string."""
    def __init__(self, response: str):
        self.response = response

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return self.response


class OpenAICompatibleLLMClient(LLMClient):
    """Minimal OpenAI-compatible chat-completions client without requiring a vendor SDK."""
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
