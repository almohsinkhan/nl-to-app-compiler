from __future__ import annotations

import os

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field

from pipeline.compiler import PipelineCompiler
from pipeline.config import (
    DEFAULT_MODELS,
    LLMConfig,
    SUPPORTED_PROVIDERS,
    is_configured,
    load_config,
    save_config,
)
from pipeline.evaluator import PipelineEvaluator
from pipeline.types import CompileResponse


app = FastAPI(title="NL App Compiler", version="1.0.0")


class CompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1)


class ConfigInitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    api_key: str = ""
    model: str | None = None
    base_url: str | None = None


@app.get("/")
def root() -> dict:
    return {
        "name": "NL App Compiler API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/status")
def config_status() -> dict:
    current = load_config()
    return {
        "configured": is_configured(),
        "supported_providers": SUPPORTED_PROVIDERS,
        "current_provider": current.provider if current else None,
        "current_model": current.model if current else None,
    }


def _save_llm_config(request: ConfigInitRequest) -> dict:
    provider = request.provider.strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        return {
            "ok": False,
            "message": f"Unsupported provider '{provider}'",
            "supported_providers": list(SUPPORTED_PROVIDERS.keys()),
        }

    model = request.model or DEFAULT_MODELS[provider]
    config = LLMConfig(
        provider=provider,
        model=model,
        api_key=request.api_key,
        base_url=request.base_url,
    )
    save_config(config)
    return {"ok": True, "provider": provider, "model": model}


@app.post("/config/init")
def config_init(request: ConfigInitRequest) -> dict:
    return _save_llm_config(request)


@app.post("/config/set")
def config_set(request: ConfigInitRequest) -> dict:
    return _save_llm_config(request)


@app.post("/compile", response_model=CompileResponse)
def compile_prompt(request: CompileRequest) -> CompileResponse:
    compiler = PipelineCompiler()
    response = compiler.compile(request.prompt)

    if not is_configured() and not response.assumptions:
        response.assumptions.append(
            "LLM provider is not configured; deterministic rule-based extraction was used."
        )

    return response


@app.post("/evaluate")
def evaluate() -> dict:
    compiler = PipelineCompiler()
    evaluator = PipelineEvaluator(compiler)
    return evaluator.run()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def run() -> None:
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError:
        port = 8000

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=_env_flag("RELOAD", False),
    )


if __name__ == "__main__":
    run()
