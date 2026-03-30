"""
Runtime orchestration layer for agent execution flows.
"""

from __future__ import annotations

import asyncio
import uuid
from time import monotonic
from typing import Any

from secnano.types import AgentInput, AgentOutput, Message, RegisteredGroup, ScheduledTask


class RuntimeOrchestrator:
    """Coordinate runtime adapter calls for message and scheduled-task flows."""

    def __init__(
        self,
        *,
        runtime_adapter: Any,
        group_queue: Any,
        channels: list[Any],
        now_utc,
        get_session_id,
        save_session,
        store_bot_message,
        record_agent_run,
        list_registered_groups,
        format_outbound,
        truncate,
        log: Any,
        find_channel,
        get_messages=None,
        format_messages=None,
        emit_trace=None,
    ) -> None:
        self.runtime_adapter = runtime_adapter
        self.group_queue = group_queue
        self.channels = channels
        self.now_utc = now_utc
        self.get_session_id = get_session_id
        self.save_session = save_session
        self.store_bot_message = store_bot_message
        self.record_agent_run = record_agent_run
        self.list_registered_groups = list_registered_groups
        self.format_outbound = format_outbound
        self.truncate = truncate
        self.log = log
        self.find_channel = find_channel
        self.get_messages = get_messages
        self.format_messages = format_messages
        self.emit_trace = emit_trace or (lambda **kwargs: None)

    async def process_group_messages(
        self,
        group: RegisteredGroup,
        messages: list[Message],
        trace_id: str | None = None,
    ) -> None:
        """Invoke the runtime adapter for a message-driven group run."""
        del messages
        chat_jid = group.jid
        channel = self.find_channel(self.channels, chat_jid)
        run_id = uuid.uuid4().hex
        effective_trace_id = trace_id or run_id
        typing_cleared = False
        close_requested = False
        started_at = self.now_utc()
        started_monotonic = monotonic()
        prompt_preview: str | None = None

        self.log.info(
            "Agent run starting",
            flow="agent_run",
            stage="start",
            run_id=run_id,
            trace_id=effective_trace_id,
            jid=chat_jid,
            folder=group.folder,
            has_channel=channel is not None,
        )
        self.emit_trace(
            trace_id=effective_trace_id,
            category="agent_run",
            stage="agent_run.started",
            status="accepted",
            jid=chat_jid,
            group_folder=group.folder,
            run_id=run_id,
        )

        recent = self.get_messages(chat_jid, limit=50)
        prompt = self.format_messages(recent, "UTC")
        prompt_preview = self.truncate(prompt)
        self.log.info(
            "Agent prompt prepared",
            flow="agent_run",
            stage="prompt_prepared",
            run_id=run_id,
            trace_id=effective_trace_id,
            jid=chat_jid,
            message_count=len(recent),
        )
        self.emit_trace(
            trace_id=effective_trace_id,
            category="agent_run",
            stage="agent_run.prompt_prepared",
            status="success",
            jid=chat_jid,
            group_folder=group.folder,
            run_id=run_id,
            details={"message_count": len(recent)},
        )

        if not prompt.strip():
            self.log.info(
                "Skipping empty prompt",
                flow="agent_run",
                stage="empty_prompt",
                run_id=run_id,
                trace_id=effective_trace_id,
                jid=chat_jid,
            )
            return

        session_id = self.get_session_id(group.folder)
        input_data = AgentInput(
            run_id=run_id,
            trace_id=effective_trace_id,
            group_folder=group.folder,
            chat_jid=chat_jid,
            is_main=bool(group.is_main),
            mode="message",
            prompt=prompt,
            session_id=session_id,
        )

        if channel:
            import contextlib

            with contextlib.suppress(Exception):
                await channel.set_typing(chat_jid, True)

        async def _on_output(output: AgentOutput) -> None:
            nonlocal typing_cleared, close_requested
            self.log.info(
                "Agent output received",
                flow="agent_run",
                stage="output_received",
                run_id=run_id,
                trace_id=effective_trace_id,
                jid=chat_jid,
                has_result=output.reply_text is not None,
                status=output.status,
            )
            self.emit_trace(
                trace_id=effective_trace_id,
                category="agent_run",
                stage="agent_run.output_received",
                status=output.status,
                jid=chat_jid,
                group_folder=group.folder,
                run_id=run_id,
            )
            if output.reply_text:
                text = self.format_outbound(output.reply_text)
                if text and channel:
                    try:
                        await channel.send_message(chat_jid, text)
                        self.store_bot_message(chat_jid, text, group.folder)
                        self.log.info(
                            "Agent reply sent",
                            flow="agent_run",
                            stage="reply_sent",
                            run_id=run_id,
                            trace_id=effective_trace_id,
                            jid=chat_jid,
                            chars=len(text),
                        )
                        self.emit_trace(
                            trace_id=effective_trace_id,
                            category="agent_run",
                            stage="agent_run.reply_sent",
                            status="success",
                            jid=chat_jid,
                            group_folder=group.folder,
                            run_id=run_id,
                        )
                    except Exception as exc:
                        self.log.error("Failed to send message", error=str(exc))

            if output.session_id:
                self.save_session(group.folder, output.session_id)

            if channel and not typing_cleared and (output.reply_text is not None or output.status == "error"):
                import contextlib

                with contextlib.suppress(Exception):
                    await channel.set_typing(chat_jid, False)
                typing_cleared = True

            if not close_requested:
                import contextlib

                with contextlib.suppress(Exception):
                    await self.group_queue.close_stdin(chat_jid)
                close_requested = True

        def _on_process(proc: asyncio.subprocess.Process, name: str, folder: str) -> None:
            self.group_queue.register_process(chat_jid, proc, name, folder)
            self.log.info(
                "Agent subprocess registered",
                flow="agent_run",
                stage="subprocess_started",
                run_id=run_id,
                trace_id=effective_trace_id,
                jid=chat_jid,
                folder=folder,
                pid=proc.pid,
                subprocess_name=name,
            )

        try:
            result = await self.runtime_adapter.run(
                group=group,
                agent_input=input_data,
                on_process=_on_process,
                on_output=_on_output,
            )

            if result.status == "error":
                self.log.error("Agent subprocess error", group=group.folder, error=result.error)
                self.emit_trace(
                    trace_id=effective_trace_id,
                    category="agent_run",
                    stage="agent_run.failed",
                    status="error",
                    jid=chat_jid,
                    group_folder=group.folder,
                    run_id=run_id,
                    details={"error": result.error} if result.error else {},
                )
            else:
                self.log.info(
                    "Agent run completed",
                    flow="agent_run",
                    stage="completed",
                    run_id=run_id,
                    trace_id=effective_trace_id,
                    jid=chat_jid,
                    had_result=result.reply_text is not None,
                )
                self.emit_trace(
                    trace_id=effective_trace_id,
                    category="agent_run",
                    stage="agent_run.completed",
                    status="success",
                    jid=chat_jid,
                    group_folder=group.folder,
                    run_id=run_id,
                )
            self.record_agent_run(
                {
                    "run_id": run_id,
                    "trace_id": effective_trace_id,
                    "kind": "message",
                    "jid": chat_jid,
                    "group_folder": group.folder,
                    "started_at": started_at,
                    "completed_at": self.now_utc(),
                    "duration_ms": int((monotonic() - started_monotonic) * 1000),
                    "status": result.status,
                    "prompt_preview": prompt_preview,
                    "reply_preview": self.truncate(
                        self.format_outbound(result.reply_text) if result.reply_text else None
                    ),
                    "prompt_full": prompt,
                    "reply_full": self.format_outbound(result.reply_text) if result.reply_text else None,
                    "error": result.error,
                }
            )
        finally:
            if channel and not typing_cleared:
                import contextlib

                with contextlib.suppress(Exception):
                    await channel.set_typing(chat_jid, False)
            self.group_queue.notify_idle(chat_jid)

    async def handle_scheduled_task(self, task: ScheduledTask) -> str | None:
        """Run a scheduled task through the runtime adapter."""
        typing_cleared = False
        close_requested = False
        started_at = self.now_utc()
        started_monotonic = monotonic()
        group = next((g for g in self.list_registered_groups() if g.folder == task.group_folder), None)
        if group is None:
            raise RuntimeError(f"Scheduled task references unknown group: {task.group_folder}")

        session_id = self.get_session_id(task.group_folder) if task.context_mode == "group" else None
        input_data = AgentInput(
            run_id=task.id,
            trace_id=task.id,
            group_folder=task.group_folder,
            chat_jid=task.chat_jid,
            is_main=bool(group.is_main),
            mode="scheduled_task",
            prompt=task.prompt,
            session_id=session_id,
        )

        channel = self.find_channel(self.channels, task.chat_jid)
        self.log.info(
            "Scheduled task execution starting",
            flow="scheduled_task",
            stage="start",
            task_id=task.id,
            trace_id=task.id,
            jid=task.chat_jid,
            group_folder=task.group_folder,
        )

        async def _on_output(output: AgentOutput) -> None:
            nonlocal typing_cleared, close_requested
            if output.reply_text and channel:
                text = self.format_outbound(output.reply_text)
                if text:
                    try:
                        await channel.send_message(task.chat_jid, text)
                        self.store_bot_message(task.chat_jid, text, task.group_folder)
                        self.log.info(
                            "Scheduled task reply sent",
                            flow="scheduled_task",
                            stage="reply_sent",
                            task_id=task.id,
                            trace_id=task.id,
                            jid=task.chat_jid,
                        )
                    except Exception as exc:
                        self.log.error("Failed to send scheduled task result", error=str(exc))
            if output.session_id and task.context_mode == "group":
                self.save_session(task.group_folder, output.session_id)
            if channel and not typing_cleared and (output.reply_text is not None or output.status == "error"):
                import contextlib

                with contextlib.suppress(Exception):
                    await channel.set_typing(task.chat_jid, False)
                typing_cleared = True
            if not close_requested:
                import contextlib

                with contextlib.suppress(Exception):
                    await self.group_queue.close_stdin(task.chat_jid)
                close_requested = True

        def _on_process(proc: asyncio.subprocess.Process, name: str, folder: str) -> None:
            self.group_queue.register_process(task.chat_jid, proc, name, folder)

        try:
            result = await self.runtime_adapter.run(
                group=group,
                agent_input=input_data,
                on_process=_on_process,
                on_output=_on_output,
            )
        finally:
            self.group_queue.notify_idle(task.chat_jid)

        if result.status == "error":
            self.record_agent_run(
                {
                    "run_id": task.id,
                    "trace_id": task.id,
                    "kind": "scheduled_task",
                    "jid": task.chat_jid,
                    "group_folder": task.group_folder,
                    "started_at": started_at,
                    "completed_at": self.now_utc(),
                    "duration_ms": int((monotonic() - started_monotonic) * 1000),
                    "status": result.status,
                    "prompt_preview": self.truncate(task.prompt),
                    "reply_preview": None,
                    "prompt_full": task.prompt,
                    "reply_full": None,
                    "error": result.error,
                }
            )
            raise RuntimeError(result.error or "Scheduled task subprocess failed")

        self.log.info(
            "Scheduled task execution completed",
            flow="scheduled_task",
            stage="completed",
            task_id=task.id,
            trace_id=task.id,
            jid=task.chat_jid,
        )
        self.record_agent_run(
            {
                "run_id": task.id,
                "trace_id": task.id,
                "kind": "scheduled_task",
                "jid": task.chat_jid,
                "group_folder": task.group_folder,
                "started_at": started_at,
                "completed_at": self.now_utc(),
                "duration_ms": int((monotonic() - started_monotonic) * 1000),
                "status": result.status,
                "prompt_preview": self.truncate(task.prompt),
                "reply_preview": self.truncate(
                    self.format_outbound(result.reply_text) if result.reply_text else None
                ),
                "prompt_full": task.prompt,
                "reply_full": self.format_outbound(result.reply_text) if result.reply_text else None,
                "error": result.error,
            }
        )
        return result.reply_text
