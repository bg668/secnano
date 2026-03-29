"""
SQLite database operations for secnano.

All database interactions go through this module. The connection is
opened lazily and kept open for the lifetime of the process.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path

from secnano.config import DB_PATH
from secnano.types import (
    Chat,
    Message,
    RegisteredGroup,
    ScheduledTask,
    Session,
    SubprocessConfig,
    TaskRunLog,
)

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            path = db_path or DB_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(path), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
        return _conn


@contextmanager
def _cursor() -> Generator[sqlite3.Cursor, None, None]:
    conn = _get_connection()
    with _lock:
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


# ── Schema ────────────────────────────────────────────────────────────────────

def init_database(db_path: Path | None = None) -> None:
    """Create tables if they do not exist."""
    conn = _get_connection(db_path)
    with _lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                jid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                last_message_time TEXT NOT NULL,
                channel TEXT NOT NULL,
                is_group INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_jid TEXT NOT NULL,
                sender TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                is_from_me INTEGER NOT NULL DEFAULT 0,
                is_bot_message INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat_jid ON messages (chat_jid);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp  ON messages (timestamp);

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                group_folder TEXT NOT NULL,
                chat_jid TEXT NOT NULL,
                prompt TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                context_mode TEXT NOT NULL DEFAULT 'group',
                next_run TEXT,
                last_run TEXT,
                last_result TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                run_at TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_task_run_logs_task_id ON task_run_logs (task_id);

            CREATE TABLE IF NOT EXISTS router_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                group_folder TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                history_path TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS registered_groups (
                jid TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                folder TEXT PRIMARY KEY,
                trigger TEXT NOT NULL,
                added_at TEXT NOT NULL,
                subprocess_config TEXT,
                requires_trigger INTEGER,
                is_main INTEGER
            );
            """
        )
        with suppress(sqlite3.OperationalError):
            conn.execute("ALTER TABLE registered_groups ADD COLUMN jid TEXT")
        conn.execute(
            """
            UPDATE registered_groups
            SET jid = trigger
            WHERE jid IS NULL OR jid = ''
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_registered_groups_jid
            ON registered_groups (jid)
            """
        )
        conn.commit()


# ── Chats ─────────────────────────────────────────────────────────────────────

def upsert_chat(chat: Chat) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO chats (jid, name, last_message_time, channel, is_group)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(jid) DO UPDATE SET
                name = excluded.name,
                last_message_time = excluded.last_message_time,
                channel = excluded.channel,
                is_group = excluded.is_group
            """,
            (chat.jid, chat.name, chat.last_message_time, chat.channel, int(chat.is_group)),
        )


def store_chat_metadata(
    chat_jid: str,
    timestamp: str,
    name: str | None = None,
    channel: str | None = None,
    is_group: bool | None = None,
) -> None:
    """
    Store chat metadata without requiring a message row.

    Existing values are preserved when optional fields are omitted.
    """
    existing = get_chat(chat_jid)
    resolved_name = name or (existing.name if existing else chat_jid)
    resolved_channel = channel or (existing.channel if existing else "unknown")
    resolved_is_group = (
        is_group if is_group is not None else (existing.is_group if existing else True)
    )

    last_message_time = timestamp
    if existing and existing.last_message_time > timestamp:
        last_message_time = existing.last_message_time

    upsert_chat(
        Chat(
            jid=chat_jid,
            name=resolved_name,
            last_message_time=last_message_time,
            channel=resolved_channel,
            is_group=resolved_is_group,
        )
    )


def get_chat(jid: str) -> Chat | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM chats WHERE jid = ?", (jid,))
        row = cur.fetchone()
    if row is None:
        return None
    return Chat(
        jid=row["jid"],
        name=row["name"],
        last_message_time=row["last_message_time"],
        channel=row["channel"],
        is_group=bool(row["is_group"]),
    )


def list_chats() -> list[Chat]:
    with _cursor() as cur:
        cur.execute("SELECT * FROM chats ORDER BY last_message_time DESC")
        rows = cur.fetchall()
    return [
        Chat(
            jid=r["jid"],
            name=r["name"],
            last_message_time=r["last_message_time"],
            channel=r["channel"],
            is_group=bool(r["is_group"]),
        )
        for r in rows
    ]


# ── Messages ──────────────────────────────────────────────────────────────────

def insert_message(msg: Message) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT OR IGNORE INTO messages
                (id, chat_jid, sender, sender_name, content, timestamp, is_from_me, is_bot_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.chat_jid,
                msg.sender,
                msg.sender_name,
                msg.content,
                msg.timestamp,
                int(msg.is_from_me),
                int(msg.is_bot_message),
            ),
        )


def get_messages(chat_jid: str, limit: int = 50) -> list[Message]:
    with _cursor() as cur:
        cur.execute(
            """
            SELECT * FROM messages
            WHERE chat_jid = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (chat_jid, limit),
        )
        rows = cur.fetchall()
    return [
        Message(
            id=r["id"],
            chat_jid=r["chat_jid"],
            sender=r["sender"],
            sender_name=r["sender_name"],
            content=r["content"],
            timestamp=r["timestamp"],
            is_from_me=bool(r["is_from_me"]),
            is_bot_message=bool(r["is_bot_message"]),
        )
        for r in reversed(rows)
    ]


def list_recent_messages(limit: int = 50) -> list[Message]:
    with _cursor() as cur:
        cur.execute(
            """
            SELECT * FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        Message(
            id=r["id"],
            chat_jid=r["chat_jid"],
            sender=r["sender"],
            sender_name=r["sender_name"],
            content=r["content"],
            timestamp=r["timestamp"],
            is_from_me=bool(r["is_from_me"]),
            is_bot_message=bool(r["is_bot_message"]),
        )
        for r in rows
    ]


# ── Scheduled Tasks ───────────────────────────────────────────────────────────

def upsert_scheduled_task(task: ScheduledTask) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO scheduled_tasks
                (id, group_folder, chat_jid, prompt, schedule_type, schedule_value,
                 context_mode, next_run, last_run, last_result, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                group_folder   = excluded.group_folder,
                chat_jid       = excluded.chat_jid,
                prompt         = excluded.prompt,
                schedule_type  = excluded.schedule_type,
                schedule_value = excluded.schedule_value,
                context_mode   = excluded.context_mode,
                next_run       = excluded.next_run,
                last_run       = excluded.last_run,
                last_result    = excluded.last_result,
                status         = excluded.status
            """,
            (
                task.id,
                task.group_folder,
                task.chat_jid,
                task.prompt,
                task.schedule_type,
                task.schedule_value,
                task.context_mode,
                task.next_run,
                task.last_run,
                task.last_result,
                task.status,
                task.created_at,
            ),
        )


def get_scheduled_task(task_id: str) -> ScheduledTask | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def list_scheduled_tasks(status: str | None = None) -> list[ScheduledTask]:
    with _cursor() as cur:
        if status:
            cur.execute("SELECT * FROM scheduled_tasks WHERE status = ?", (status,))
        else:
            cur.execute("SELECT * FROM scheduled_tasks")
        rows = cur.fetchall()
    return [_row_to_task(r) for r in rows]


def update_task_next_run(task_id: str, next_run: str | None, last_run: str) -> None:
    with _cursor() as cur:
        cur.execute(
            "UPDATE scheduled_tasks SET next_run = ?, last_run = ? WHERE id = ?",
            (next_run, last_run, task_id),
        )


def update_task_last_result(task_id: str, result: str | None) -> None:
    with _cursor() as cur:
        cur.execute(
            "UPDATE scheduled_tasks SET last_result = ? WHERE id = ?",
            (result, task_id),
        )


def _row_to_task(row: sqlite3.Row) -> ScheduledTask:
    return ScheduledTask(
        id=row["id"],
        group_folder=row["group_folder"],
        chat_jid=row["chat_jid"],
        prompt=row["prompt"],
        schedule_type=row["schedule_type"],
        schedule_value=row["schedule_value"],
        context_mode=row["context_mode"],
        next_run=row["next_run"],
        last_run=row["last_run"],
        last_result=row["last_result"],
        status=row["status"],
        created_at=row["created_at"],
    )


# ── Task Run Logs ─────────────────────────────────────────────────────────────

def insert_task_run_log(log: TaskRunLog) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_run_logs (task_id, run_at, duration_ms, status, result, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (log.task_id, log.run_at, log.duration_ms, log.status, log.result, log.error),
        )


def get_task_run_logs(task_id: str, limit: int = 20) -> list[TaskRunLog]:
    with _cursor() as cur:
        cur.execute(
            """
            SELECT * FROM task_run_logs WHERE task_id = ?
            ORDER BY run_at DESC LIMIT ?
            """,
            (task_id, limit),
        )
        rows = cur.fetchall()
    return [
        TaskRunLog(
            task_id=r["task_id"],
            run_at=r["run_at"],
            duration_ms=r["duration_ms"],
            status=r["status"],
            result=r["result"],
            error=r["error"],
        )
        for r in rows
    ]


def list_recent_task_run_logs(limit: int = 20) -> list[TaskRunLog]:
    with _cursor() as cur:
        cur.execute(
            """
            SELECT * FROM task_run_logs
            ORDER BY run_at DESC LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        TaskRunLog(
            task_id=r["task_id"],
            run_at=r["run_at"],
            duration_ms=r["duration_ms"],
            status=r["status"],
            result=r["result"],
            error=r["error"],
        )
        for r in rows
    ]


# ── Router State ──────────────────────────────────────────────────────────────

def get_router_state(key: str) -> str | None:
    with _cursor() as cur:
        cur.execute("SELECT value FROM router_state WHERE key = ?", (key,))
        row = cur.fetchone()
    return row["value"] if row else None


def set_router_state(key: str, value: str) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO router_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def delete_router_state(key: str) -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM router_state WHERE key = ?", (key,))


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_session(group_folder: str) -> Session | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM sessions WHERE group_folder = ?", (group_folder,))
        row = cur.fetchone()
    if row is None:
        return None
    return Session(
        group_folder=row["group_folder"],
        session_id=row["session_id"],
        history_path=row["history_path"],
        updated_at=row["updated_at"],
    )


def upsert_session(session: Session) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO sessions (group_folder, session_id, history_path, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(group_folder) DO UPDATE SET
                session_id   = excluded.session_id,
                history_path = excluded.history_path,
                updated_at   = excluded.updated_at
            """,
            (
                session.group_folder,
                session.session_id,
                session.history_path,
                session.updated_at,
            ),
        )


def delete_session(group_folder: str) -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE group_folder = ?", (group_folder,))


def list_sessions() -> list[Session]:
    with _cursor() as cur:
        cur.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
        rows = cur.fetchall()
    return [
        Session(
            group_folder=row["group_folder"],
            session_id=row["session_id"],
            history_path=row["history_path"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


# ── Registered Groups ─────────────────────────────────────────────────────────

def _row_to_group(row: sqlite3.Row) -> RegisteredGroup:
    import json

    sp_raw = row["subprocess_config"]
    subprocess_config: SubprocessConfig | None = None
    if sp_raw:
        data = json.loads(sp_raw)
        subprocess_config = SubprocessConfig(
            timeout=data.get("timeout"),
        )

    return RegisteredGroup(
        jid=row["jid"],
        name=row["name"],
        folder=row["folder"],
        trigger=row["trigger"],
        added_at=row["added_at"],
        subprocess_config=subprocess_config,
        requires_trigger=(
            bool(row["requires_trigger"]) if row["requires_trigger"] is not None else None
        ),
        is_main=bool(row["is_main"]) if row["is_main"] is not None else None,
    )


def upsert_registered_group(group: RegisteredGroup) -> None:
    import json

    sp_json: str | None = None
    if group.subprocess_config:
        sp_json = json.dumps(
            {"timeout": group.subprocess_config.timeout}
        )

    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO registered_groups
                (jid, name, folder, trigger, added_at, subprocess_config, requires_trigger, is_main)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(folder) DO UPDATE SET
                jid               = excluded.jid,
                name              = excluded.name,
                trigger           = excluded.trigger,
                added_at          = excluded.added_at,
                subprocess_config = excluded.subprocess_config,
                requires_trigger  = excluded.requires_trigger,
                is_main           = excluded.is_main
            """,
            (
                group.jid,
                group.name,
                group.folder,
                group.trigger,
                group.added_at,
                sp_json,
                int(group.requires_trigger) if group.requires_trigger is not None else None,
                int(group.is_main) if group.is_main is not None else None,
            ),
        )


def get_registered_group(folder: str) -> RegisteredGroup | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM registered_groups WHERE folder = ?", (folder,))
        row = cur.fetchone()
    return _row_to_group(row) if row else None


def get_registered_group_by_jid(jid: str) -> RegisteredGroup | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM registered_groups WHERE jid = ?", (jid,))
        row = cur.fetchone()
    return _row_to_group(row) if row else None


def list_registered_groups() -> list[RegisteredGroup]:
    with _cursor() as cur:
        cur.execute("SELECT * FROM registered_groups ORDER BY added_at")
        rows = cur.fetchall()
    return [_row_to_group(r) for r in rows]


def delete_registered_group(folder: str) -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM registered_groups WHERE folder = ?", (folder,))
