from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from pipeline.config import DEFAULT_BASE_URLS, LLMConfig


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        return self._openai_compatible_json(system_prompt, user_prompt)

    def _openai_compatible_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        base_url = self.config.base_url or DEFAULT_BASE_URLS["groq"]
        if not base_url:
            raise LLMError("Missing base_url for provider")

        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        api_key = self.config.api_key.strip()
        if not api_key:
            raise LLMError("Groq provider requires a non-empty api_key")
        headers["Authorization"] = f"Bearer {api_key}"

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"LLM error {resp.status_code}: {resp.text}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return _extract_json(content)


def _extract_json(content: str) -> Dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMError("No JSON object found in model response")
        return json.loads(content[start : end + 1])
