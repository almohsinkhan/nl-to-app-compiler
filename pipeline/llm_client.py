from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx

from pipeline.config import DEFAULT_BASE_URLS, LLMConfig


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        provider = self.config.provider.lower().strip()
        if provider == "anthropic":
            return self._anthropic_json(system_prompt, user_prompt)
        return self._openai_compatible_json(system_prompt, user_prompt)

    def _openai_compatible_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        base_url = self.config.base_url or DEFAULT_BASE_URLS.get(self.config.provider, "")
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
        if api_key:
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

    def _anthropic_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        api_key = self.config.api_key.strip()
        if not api_key:
            raise LLMError("Anthropic provider requires a non-empty api_key")

        base_url = self.config.base_url or DEFAULT_BASE_URLS["anthropic"]
        url = f"{base_url.rstrip('/')}/messages"
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "max_tokens": 2000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"Anthropic error {resp.status_code}: {resp.text}")

        data = resp.json()
        parts: List[Dict[str, Any]] = data.get("content", [])
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        return _extract_json(text)


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
