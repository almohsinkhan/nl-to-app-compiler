from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


import os
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path("config.local.json")
GROQ_PROVIDER = "groq"
_MANAGED_KEY_PLACEHOLDER = "REPLACE_WITH_YOUR_MANAGED_GROQ_API_KEY"
MANAGED_GROQ_API_KEY = os.getenv("MANAGED_GROQ_API_KEY", _MANAGED_KEY_PLACEHOLDER)


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="Provider slug. Only 'groq' is supported.")
    model: str
    api_key: str
    base_url: Optional[str] = None
    timeout_seconds: int = 60

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider != GROQ_PROVIDER:
            raise ValueError("Only 'groq' provider is supported")
        return provider


SUPPORTED_PROVIDERS = {
    GROQ_PROVIDER: "Groq Cloud OpenAI-compatible endpoint",
}


DEFAULT_MODELS = {
    GROQ_PROVIDER: "llama-3.1-70b-versatile",
}


DEFAULT_BASE_URLS = {
    GROQ_PROVIDER: "https://api.groq.com/openai/v1",
}


def get_managed_api_key() -> str:
    return MANAGED_GROQ_API_KEY.strip()


def _default_config() -> LLMConfig:
    return LLMConfig(
        provider=GROQ_PROVIDER,
        model=DEFAULT_MODELS[GROQ_PROVIDER],
        api_key=get_managed_api_key(),
        base_url=DEFAULT_BASE_URLS[GROQ_PROVIDER],
    )


def load_config() -> Optional[LLMConfig]:
    default = _default_config()
    if not CONFIG_PATH.exists():
        return default
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default

    provider = str(raw.get("provider", GROQ_PROVIDER)).strip().lower() or GROQ_PROVIDER
    if provider != GROQ_PROVIDER:
        return default

    model = str(raw.get("model", "")).strip() or default.model
    base_url = raw.get("base_url")
    if isinstance(base_url, str):
        base_url = base_url.strip() or default.base_url
    else:
        base_url = default.base_url
    timeout_seconds = raw.get("timeout_seconds", default.timeout_seconds)
    try:
        timeout_seconds = int(timeout_seconds)
    except (TypeError, ValueError):
        timeout_seconds = default.timeout_seconds

    try:
        return LLMConfig(
            provider=provider,
            model=model,
            api_key=get_managed_api_key(),
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    except ValidationError:
        return default


def save_config(config: LLMConfig) -> None:
    payload = {
        "provider": config.provider,
        "model": config.model,
        "base_url": config.base_url,
        "timeout_seconds": config.timeout_seconds,
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_configured() -> bool:
    key = get_managed_api_key()
    return bool(key and key != _MANAGED_KEY_PLACEHOLDER)
