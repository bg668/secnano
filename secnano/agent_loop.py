from __future__ import annotations

from typing import Any, Callable


def run_agent_loop(
    messages: list[dict],
    tools: list[dict],
    tool_handlers: dict[str, Callable[..., str]],
    system: str = "",
    max_rounds: int = 50,
) -> str:
    """Standard agent loop: call LLM, execute tool_use blocks, repeat until done.

    Returns the final text from the assistant.
    """
    from .llm_client import call_llm

    final_text = ""
    for _ in range(max_rounds):
        response = call_llm(messages, tools=tools or None, system=system)
        stop_reason = response.get("stop_reason")
        content: list[dict[str, Any]] = response.get("content", [])

        # Collect final text from text blocks
        assistant_text_parts = [
            block["text"] for block in content if block.get("type") == "text"
        ]
        if assistant_text_parts:
            final_text = "\n".join(assistant_text_parts)

        # Append assistant response to messages
        messages.append({"role": "assistant", "content": content})

        if stop_reason != "tool_use":
            break

        # Execute all tool_use blocks and collect results
        tool_results: list[dict[str, Any]] = []
        for block in content:
            if block.get("type") != "tool_use":
                continue
            tool_name: str = block.get("name", "")
            tool_input: dict = block.get("input", {})
            tool_use_id: str = block.get("id", "")

            handler = tool_handlers.get(tool_name)
            if handler is None:
                result_content = f"Unknown tool: {tool_name}"
            else:
                try:
                    result_content = handler(**tool_input)
                except Exception as exc:
                    result_content = f"Tool error ({tool_name}): {exc}"

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_content,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return final_text
