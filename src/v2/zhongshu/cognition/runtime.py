from __future__ import annotations

import os

from src.v2.providers.base import AIProvider, RuleBasedProvider
from src.v2.providers.openai import OpenAIProvider
from src.v2.schemas.cognition import CognitionRequest, CognitionResult
from src.v2.schemas.task import ExecutionRequest

from .prompting import build_prompt


def _select_provider(provider: AIProvider | None = None) -> AIProvider:
    if provider is not None:
        return provider

    configured = os.environ.get("SECNANO_PROVIDER", "rule_based").lower()
    if configured == "openai":
        return OpenAIProvider()
    return RuleBasedProvider()


def _parse_to_execution_request(task_id: str, content: str) -> ExecutionRequest:
    normalized = content.replace("\n", " ").strip()
    if normalized.startswith("TOOL:") and " ARGS:" in normalized:
        head, args = normalized.split(" ARGS:", 1)
        tool_name = head.split("TOOL:", 1)[1].strip() or "echo"
        argv = tuple(token for token in args.strip().split(" ") if token)
        return ExecutionRequest(task_id=task_id, tool_name=tool_name, arguments=argv)
    return ExecutionRequest(task_id=task_id, tool_name="echo", arguments=(content.strip() or "ok",))


def run_cognition(request: CognitionRequest, provider: AIProvider | None = None) -> CognitionResult:
    selected = _select_provider(provider)
    prompt = build_prompt(request)
    model_output = selected.generate(prompt)
    return CognitionResult(
        thought=model_output,
        execution_request=_parse_to_execution_request(request.inbound.task_id, model_output),
    )
