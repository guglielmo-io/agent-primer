from __future__ import annotations

import json
from typing import Any

import httpx

from agent_primer.models import ModelInfo


class OpenRouterClient:
    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 90.0) -> None:
        self.api_key = api_key
        self.transport = transport
        self.timeout = timeout

    async def list_models(self) -> list[ModelInfo]:
        async with self._client() as client:
            response = await client.get("/models")
            response.raise_for_status()
        data = response.json().get("data", [])
        return [ModelInfo.model_validate(item) for item in data]

    async def complete_json(
        self,
        model: str,
        prompt: str,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        content = await self._complete(model, prompt, reasoning_effort=reasoning_effort, verbosity=verbosity)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            repair_prompt = f"{prompt}\n\nReturn only valid JSON matching the requested schema. Do not add markdown."
            repaired = await self._complete(model, repair_prompt, reasoning_effort=reasoning_effort, verbosity=verbosity)
            return json.loads(repaired)

    async def _complete(
        self,
        model: str,
        prompt: str,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not verbosity:
            payload["temperature"] = 0.2
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}
        if verbosity:
            payload["verbosity"] = verbosity
        async with self._client() as client:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "local-agent-primer",
                "X-Title": "Agent Primer",
            },
            timeout=self.timeout,
            transport=self.transport,
        )
