"""
Runtime adapter layer for host-side agent execution.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from secnano.subprocess_runner import run_subprocess_agent
from secnano.types import (
    AgentInput,
    AgentOutput,
    RegisteredGroup,
    SubprocessInput,
    SubprocessOutput,
)

ProcessCallback = Callable[[asyncio.subprocess.Process, str, str], None]
OutputCallback = Callable[[AgentOutput], Awaitable[None]]
RunAgentFn = Callable[
    [RegisteredGroup, SubprocessInput, ProcessCallback, Callable[[SubprocessOutput], Awaitable[None]] | None],
    Awaitable[SubprocessOutput],
]


class SubprocessRuntimeAdapter:
    """Runtime adapter v1 backed by the current subprocess runner."""

    def __init__(self, run_agent: RunAgentFn | None = None) -> None:
        self._run_agent = run_agent or run_subprocess_agent

    async def run(
        self,
        *,
        group: RegisteredGroup,
        agent_input: AgentInput,
        on_process: ProcessCallback,
        on_output: OutputCallback | None = None,
    ) -> AgentOutput:
        async def _forward_output(output: SubprocessOutput) -> None:
            if on_output is None:
                return
            await on_output(
                AgentOutput(
                    run_id=agent_input.run_id,
                    status=output.status,
                    reply_text=output.result,
                    session_id=output.new_session_id,
                    error=output.error,
                )
            )

        result = await self._run_agent(
            group=group,
            input_data=SubprocessInput(
                prompt=agent_input.prompt,
                group_folder=agent_input.group_folder,
                chat_jid=agent_input.chat_jid,
                is_main=agent_input.is_main,
                session_id=agent_input.session_id,
                is_scheduled_task=agent_input.mode == "scheduled_task",
            ),
            on_process=on_process,
            on_output=_forward_output if on_output is not None else None,
        )

        return AgentOutput(
            run_id=agent_input.run_id,
            status=result.status,
            reply_text=result.result,
            session_id=result.new_session_id,
            error=result.error,
        )
