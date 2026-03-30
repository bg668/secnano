"""
Type definitions for secnano.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdditionalMount:
    """Describes an additional filesystem mount for a subprocess workspace."""

    host_path: str
    container_path: str | None = None
    readonly: bool = True


@dataclass
class SubprocessConfig:
    """Configuration for the agent subprocess."""

    additional_mounts: list[AdditionalMount] | None = None
    timeout: int | None = None


@dataclass
class RegisteredGroup:
    """A registered group/conversation that the orchestrator manages."""

    jid: str
    name: str
    folder: str
    trigger: str
    added_at: str
    subprocess_config: SubprocessConfig | None = None
    requires_trigger: bool | None = None  # Default: True for groups
    is_main: bool | None = None


@dataclass
class NewMessage:
    """A new incoming message from a channel."""

    id: str
    chat_jid: str
    sender: str
    sender_name: str
    content: str
    timestamp: str
    is_from_me: bool = False
    is_bot_message: bool = False


@dataclass
class ChatMetadata:
    """Chat/group metadata discovered by channels or IPC bridges."""

    chat_jid: str
    timestamp: str
    name: str | None = None
    channel: str | None = None
    is_group: bool | None = None


@dataclass
class IpcTaskRequest:
    """A generic task request read from ``data/ipc/{source_group}/tasks``."""

    id: str
    source_group: str
    type: str
    payload: dict[str, Any]
    timestamp: str | None = None


@dataclass
class ScheduledTask:
    """A scheduled task definition."""

    id: str
    group_folder: str
    chat_jid: str
    prompt: str
    schedule_type: str  # 'cron' | 'interval' | 'once'
    schedule_value: str
    context_mode: str  # 'group' | 'isolated'
    next_run: str | None
    last_run: str | None
    last_result: str | None
    status: str  # 'active' | 'paused' | 'completed'
    created_at: str


@dataclass
class TaskRunLog:
    """A log entry for a scheduled task run."""

    task_id: str
    run_at: str
    duration_ms: int
    status: str  # 'success' | 'error'
    result: str | None
    error: str | None


@dataclass
class SubprocessOutput:
    """Output from an agent subprocess invocation."""

    status: str  # 'success' | 'error'
    result: str | None
    new_session_id: str | None = None
    error: str | None = None


@dataclass
class TraceEvent:
    """Stable trace event used for host flow assertions and replay."""

    event_id: str
    trace_id: str
    timestamp: str
    category: str
    stage: str
    status: str
    jid: str | None = None
    group_folder: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    source: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInput:
    """Stable host-to-runtime contract."""

    run_id: str
    trace_id: str
    group_folder: str
    chat_jid: str
    is_main: bool
    mode: str  # "message" | "scheduled_task"
    prompt: str
    session_id: str | None = None
    context_refs: list[str] | None = None


@dataclass
class AgentOutput:
    """Stable runtime-to-host contract."""

    run_id: str
    status: str  # "success" | "error" | "partial"
    reply_text: str | None
    session_id: str | None = None
    error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


class Channel(ABC):
    """Abstract base class for messaging channels."""

    name: str

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the channel."""
        ...

    @abstractmethod
    async def send_message(self, jid: str, text: str) -> None:
        """Send a text message to the given JID."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the channel is currently connected."""
        ...

    @abstractmethod
    def owns_jid(self, jid: str) -> bool:
        """Return True if this channel owns/handles the given JID."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the channel."""
        ...

    async def set_typing(self, jid: str, is_typing: bool) -> None:
        """Optionally set typing indicator. Default: no-op."""
        return

    async def sync_groups(self, force: bool = False) -> None:
        """Optionally sync group list. Default: no-op."""
        return


@dataclass
class Chat:
    """A chat record stored in the database."""

    jid: str
    name: str
    last_message_time: str
    channel: str
    is_group: bool = False


@dataclass
class Message:
    """A message record stored in the database."""

    id: str
    chat_jid: str
    sender: str
    sender_name: str
    content: str
    timestamp: str
    is_from_me: bool = False
    is_bot_message: bool = False


@dataclass
class Session:
    """A session record linking a group folder to a session ID and history file."""

    group_folder: str
    session_id: str
    history_path: str
    updated_at: str


@dataclass
class SubprocessInput:
    """Input passed to the agent subprocess via stdin."""

    prompt: str
    group_folder: str
    chat_jid: str
    is_main: bool
    session_id: str | None = None
    is_scheduled_task: bool = False
    assistant_name: str = "Andy"
