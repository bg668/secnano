"""
Per-group message queue with asyncio-based concurrency control.

Each group has its own queue. Only one agent subprocess runs per group at
a time; additional messages are queued and delivered via the IPC protocol.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from secnano.config import DATA_DIR
from secnano.logger import get_logger

log = get_logger("group_queue")

IPC_INPUT_DIR_NAME = "input"
IPC_CLOSE_SENTINEL = "_close"


@dataclass
class _QueueEntry:
    task_id: str
    fn: Callable[[], Awaitable[None]]


@dataclass
class _GroupState:
    queue: asyncio.Queue[_QueueEntry] = field(default_factory=asyncio.Queue)
    running: bool = False
    current_proc: Optional[asyncio.subprocess.Process] = None
    subprocess_name: Optional[str] = None
    group_folder: Optional[str] = None
    idle_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self.idle_event.set()  # Initially idle


ProcessMessagesFn = Callable[[str, list[dict]], Awaitable[None]]


class GroupQueue:
    """
    Manages per-group task queues.

    Only one coroutine runs per group at a time; extras wait in the queue.
    """

    def __init__(self) -> None:
        self._states: dict[str, _GroupState] = defaultdict(_GroupState)
        self._process_messages_fn: Optional[ProcessMessagesFn] = None
        self._lock = asyncio.Lock()

    def set_process_messages_fn(self, fn: ProcessMessagesFn) -> None:
        """Register the function that processes a group's pending messages."""
        self._process_messages_fn = fn

    def _state(self, group_jid: str) -> _GroupState:
        if group_jid not in self._states:
            self._states[group_jid] = _GroupState()
        return self._states[group_jid]

    async def enqueue_message_check(self, group_jid: str) -> None:
        """
        Enqueue a message-processing check for *group_jid*.

        If the group is idle, the check runs immediately.
        """
        if self._process_messages_fn is None:
            log.warning("process_messages_fn not set; dropping message check", jid=group_jid)
            return

        fn = self._process_messages_fn
        task_id = str(uuid.uuid4())

        async def _run() -> None:
            await fn(group_jid, [])

        await self._enqueue(group_jid, task_id, _run)

    async def enqueue_task(
        self,
        group_jid: str,
        task_id: str,
        fn: Callable[[], Awaitable[None]],
    ) -> None:
        """Enqueue an arbitrary async task for *group_jid*."""
        await self._enqueue(group_jid, task_id, fn)

    async def _enqueue(
        self,
        group_jid: str,
        task_id: str,
        fn: Callable[[], Awaitable[None]],
    ) -> None:
        state = self._state(group_jid)
        entry = _QueueEntry(task_id=task_id, fn=fn)
        await state.queue.put(entry)

        if not state.running:
            asyncio.create_task(self._drain(group_jid))

    async def _drain(self, group_jid: str) -> None:
        """Drain the queue for *group_jid* sequentially."""
        state = self._state(group_jid)
        if state.running:
            return
        state.running = True
        state.idle_event.clear()

        try:
            while not state.queue.empty():
                entry = await state.queue.get()
                try:
                    await entry.fn()
                except Exception as exc:
                    log.error("Queue task error", jid=group_jid, task=entry.task_id, error=str(exc))
                finally:
                    state.queue.task_done()
        finally:
            state.running = False
            state.idle_event.set()

    def register_process(
        self,
        group_jid: str,
        proc: asyncio.subprocess.Process,
        subprocess_name: str,
        group_folder: str,
    ) -> None:
        """Register the active subprocess for *group_jid*."""
        state = self._state(group_jid)
        state.current_proc = proc
        state.subprocess_name = subprocess_name
        state.group_folder = group_folder

    def notify_idle(self, group_jid: str) -> None:
        """Signal that *group_jid*'s subprocess has finished."""
        state = self._state(group_jid)
        state.current_proc = None
        state.subprocess_name = None

    async def send_message(self, group_jid: str, text: str) -> None:
        """
        Deliver *text* to an active subprocess via the IPC input directory.

        Writes a JSON file to ``data/ipc/{group_folder}/input/``.
        """
        state = self._state(group_jid)
        folder = state.group_folder
        if not folder:
            log.warning("No active subprocess for group; cannot send IPC message", jid=group_jid)
            return

        ipc_input_dir = DATA_DIR / "ipc" / folder / IPC_INPUT_DIR_NAME
        ipc_input_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.json"
        payload = json.dumps({"content": text})
        (ipc_input_dir / filename).write_text(payload, encoding="utf-8")
        log.debug("IPC message written", jid=group_jid, file=filename)

    async def close_stdin(self, group_jid: str) -> None:
        """
        Send the close sentinel to an active subprocess.

        Writes ``data/ipc/{group_folder}/input/_close``.
        """
        state = self._state(group_jid)
        folder = state.group_folder
        if not folder:
            return

        ipc_input_dir = DATA_DIR / "ipc" / folder / IPC_INPUT_DIR_NAME
        ipc_input_dir.mkdir(parents=True, exist_ok=True)
        (ipc_input_dir / IPC_CLOSE_SENTINEL).write_text("", encoding="utf-8")
        log.debug("IPC close sentinel written", jid=group_jid)

    async def wait_idle(self, group_jid: str, timeout: float = 30.0) -> bool:
        """
        Wait until the group is idle.

        Returns True if the group became idle within *timeout* seconds.
        """
        state = self._state(group_jid)
        try:
            await asyncio.wait_for(state.idle_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def shutdown(self, grace_period_ms: int = 5000) -> None:
        """Gracefully shut down all group queues."""
        grace = grace_period_ms / 1000.0
        tasks = []
        for jid, state in self._states.items():
            if state.current_proc and state.current_proc.returncode is None:
                log.info("Terminating subprocess", jid=jid)
                try:
                    state.current_proc.terminate()
                except ProcessLookupError:
                    pass
                tasks.append(asyncio.create_task(state.idle_event.wait()))

        if tasks:
            await asyncio.wait(tasks, timeout=grace)
