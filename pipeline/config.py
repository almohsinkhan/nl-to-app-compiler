from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


CONFIG_PATH = Path("config.local.json")


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="Provider slug, e.g. openai, anthropic, custom")
    model: str
    api_key: str
    base_url: Optional[str] = None
    timeout_seconds: int = 60


SUPPORTED_PROVIDERS = {
    "openai": "OpenAI Chat Completions",
    "anthropic": "Anthropic Messages",
    "google": "Google Gemini OpenAI-compatible endpoint",
    "openrouter": "OpenRouter OpenAI-compatible endpoint",
    "groq": "Groq OpenAI-compatible endpoint",
    "together": "Together OpenAI-compatible endpoint",
    "ollama": "Local Ollama OpenAI-compatible endpoint",
    "custom": "Any OpenAI-compatible endpoint",
}


DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "google": "gemini-1.5-pro",
    "openrouter": "openai/gpt-4o-mini",
    "groq": "llama-3.1-70b-versatile",
    "together": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "ollama": "llama3.1",
    "custom": "gpt-4o-mini",
}


DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": "",
}


def load_config() -> Optional[LLMConfig]:
    if not CONFIG_PATH.exists():
        return None
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return LLMConfig.model_validate(raw)


def save_config(config: LLMConfig) -> None:
    CONFIG_PATH.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def is_configured() -> bool:
    return CONFIG_PATH.exists()
