from __future__ import annotations

from pipeline.config import (
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    LLMConfig,
    SUPPORTED_PROVIDERS,
    save_config,
)


def main() -> None:
    providers = list(SUPPORTED_PROVIDERS.keys())
    print("Select LLM provider:")
    for idx, provider in enumerate(providers, start=1):
        print(f"{idx}. {provider} - {SUPPORTED_PROVIDERS[provider]}")

    selection = input("Enter choice number: ").strip()
    if not selection.isdigit() or int(selection) < 1 or int(selection) > len(providers):
        raise SystemExit("Invalid selection")

    provider = providers[int(selection) - 1]
    default_model = DEFAULT_MODELS[provider]
    default_base_url = DEFAULT_BASE_URLS.get(provider, "")

    model = input(f"Model [{default_model}]: ").strip() or default_model
    api_key = input("API key: ").strip()
    if not api_key:
        raise SystemExit("API key is required")

    base_url_prompt = f"Base URL [{default_base_url}]: " if default_base_url else "Base URL: "
    base_url = input(base_url_prompt).strip() or default_base_url or None

    config = LLMConfig(provider=provider, model=model, api_key=api_key, base_url=base_url)
    save_config(config)
    print("Saved config.local.json")


if __name__ == "__main__":
    main()
