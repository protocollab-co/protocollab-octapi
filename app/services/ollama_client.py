from __future__ import annotations

from typing import Any
import httpx


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def health(self) -> bool:
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models", [])
            return any(item.get("name", "") == self.model for item in models)

    async def generate_yaml_text(self, prompt: str, context: dict[str, Any] | None, system_prompt: str) -> str:
        timeout = httpx.Timeout(self.timeout_seconds)
        payload = {
            "model": self.model,
            "prompt": self._compose_prompt(prompt, context, system_prompt),
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "num_predict": 256,
                "batch": 1,
                "parallel": 1,
            },
        }
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    @staticmethod
    def _compose_prompt(prompt: str, context: dict[str, Any] | None, system_prompt: str) -> str:
        import json
        context_block = json.dumps(context, ensure_ascii=False, sort_keys=True) if context is not None else "{}"
        return (
            f"{system_prompt}\n\n"
            f"User task:\n{prompt}\n\n"
            f"Runtime context (optional):\n{context_block}\n\n"
            "Output only YAML."
        )
