from __future__ import annotations

import os
from typing import Any


def call_llm(
    messages: list[dict],
    tools: list[dict] | None = None,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict:
    """Call Anthropic Claude LLM and return the raw response as a dict.

    Reads ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) from environment.
    Supports ANTHROPIC_BASE_URL override and SECNANO_MODEL for model selection.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package is not installed. Run: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise RuntimeError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN "
            "environment variable before starting workers."
        )

    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    resolved_model = model or os.environ.get("SECNANO_MODEL", "claude-3-5-haiku-20241022")

    kwargs: dict[str, Any] = {
        "api_key": api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**kwargs)

    create_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        create_kwargs["system"] = system
    if tools:
        create_kwargs["tools"] = tools

    response = client.messages.create(**create_kwargs)
    return response.model_dump()
