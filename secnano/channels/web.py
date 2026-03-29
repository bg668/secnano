"""
Local web channel for MVP development and bootstrap flows.

Provides a minimal browser-based chat UI backed by a built-in HTTP server.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from secnano.logger import get_logger
from secnano.types import Channel, ChatMetadata, Message, NewMessage

log = get_logger("channels.web")


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


class LocalWebChannel(Channel):
    """Serve a local chat page and bridge it into the orchestrator."""

    name = "web"

    def __init__(
        self,
        on_message,
        on_chat_metadata,
        *,
        host: str,
        port: int,
        chat_jid: str,
        chat_name: str,
        history_loader: Callable[[], list[Message]] | None = None,
        ops_snapshot: Callable[[str | None, str | None], dict[str, Any]] | None = None,
    ) -> None:
        self._on_message = on_message
        self._on_chat_metadata = on_chat_metadata
        self._host = host
        self._port = port
        self._chat_jid = chat_jid
        self._chat_name = chat_name
        self._history_loader = history_loader
        self._ops_snapshot = ops_snapshot
        self._loop: asyncio.AbstractEventLoop | None = None
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._server_ready = threading.Event()
        self._startup_error: Exception | None = None
        self._messages: list[dict[str, Any]] = []
        self._messages_lock = threading.Lock()
        self._next_message_id = 0
        self._typing = False

    @property
    def url(self) -> str:
        port = self._bound_port()
        host = "127.0.0.1" if self._host in {"0.0.0.0", "::"} else self._host
        return f"http://{host}:{port}"

    @property
    def chat_jid(self) -> str:
        return self._chat_jid

    def _bound_port(self) -> int:
        if self._httpd is None:
            return self._port
        return int(self._httpd.server_address[1])

    def _append_message(
        self,
        role: str,
        text: str,
        *,
        timestamp: str | None = None,
        author: str | None = None,
    ) -> int:
        with self._messages_lock:
            self._next_message_id += 1
            message_id = self._next_message_id
            self._messages.append(
                {
                    "id": message_id,
                    "role": role,
                    "text": text,
                    "timestamp": timestamp or _now_utc(),
                    "author": author or ("Assistant" if role == "assistant" else "Web User"),
                }
            )
            return message_id

    def _seed_history(self) -> None:
        if self._history_loader is None:
            return
        with self._messages_lock:
            if self._messages:
                return
        try:
            history = self._history_loader()
        except Exception as exc:
            log.error("Failed to load web chat history", error=str(exc))
            return
        for message in history:
            role = "assistant" if message.is_from_me or message.is_bot_message else "user"
            author = (
                self._chat_name
                if role == "assistant"
                else (message.sender_name or message.sender or "User")
            )
            self._append_message(
                role,
                message.content,
                timestamp=message.timestamp,
                author=author,
            )

    def _messages_since(self, since: int) -> dict[str, Any]:
        with self._messages_lock:
            items = [message for message in self._messages if int(message["id"]) > since]
            next_since = self._next_message_id
            typing = self._typing
        return {
            "messages": items,
            "next_since": next_since,
            "typing": typing,
            "chat_jid": self._chat_jid,
            "chat_name": self._chat_name,
        }

    def _dispatch_inbound_message(self, text: str) -> None:
        if self._loop is None:
            raise RuntimeError("Web channel event loop is not ready")

        self._append_message("user", text)
        future = asyncio.run_coroutine_threadsafe(
            self._on_message(
                NewMessage(
                    id=str(uuid.uuid4()),
                    chat_jid=self._chat_jid,
                    sender="web-user",
                    sender_name="Web User",
                    content=text,
                    timestamp=_now_utc(),
                )
            ),
            self._loop,
        )

        def _log_result(done) -> None:
            try:
                done.result()
            except Exception as exc:
                log.error("Web inbound message callback failed", error=str(exc))

        future.add_done_callback(_log_result)

    def _render_page(self) -> str:
        title = escape(self._chat_name)
        chat_jid = escape(self._chat_jid)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: rgba(255, 252, 246, 0.92);
      --ink: #1f1a17;
      --muted: #6a625b;
      --accent: #a54d2d;
      --accent-soft: #f0d7cb;
      --border: rgba(31, 26, 23, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top, rgba(165, 77, 45, 0.18), transparent 40%),
        linear-gradient(135deg, #efe6d6, #f7f4ed 55%, #ebe1d0);
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    main {{
      width: min(900px, 100%);
      height: min(760px, calc(100vh - 48px));
      display: grid;
      grid-template-rows: auto 1fr auto;
      border: 1px solid var(--border);
      border-radius: 24px;
      background: var(--panel);
      backdrop-filter: blur(12px);
      overflow: hidden;
      box-shadow: 0 28px 70px rgba(61, 40, 24, 0.18);
    }}
    header {{
      padding: 20px 24px 12px;
      border-bottom: 1px solid var(--border);
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1;
    }}
    header p {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}
    #messages {{
      overflow-y: auto;
      padding: 20px 20px 12px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .message {{
      max-width: min(720px, 88%);
      padding: 14px 16px;
      border-radius: 18px;
      white-space: pre-wrap;
      line-height: 1.45;
      animation: rise 160ms ease-out;
    }}
    .user {{
      align-self: flex-end;
      background: var(--accent);
      color: #fffaf7;
    }}
    .assistant {{
      align-self: flex-start;
      background: var(--accent-soft);
    }}
    .meta {{
      margin-top: 6px;
      font-size: 12px;
      opacity: 0.72;
    }}
    #typing {{
      min-height: 20px;
      padding: 0 24px;
      color: var(--muted);
      font-size: 14px;
    }}
    form {{
      border-top: 1px solid var(--border);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 16px 20px 20px;
      background: rgba(255, 248, 240, 0.9);
    }}
    textarea {{
      resize: none;
      min-height: 72px;
      max-height: 180px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--border);
      font: inherit;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.92);
    }}
    button {{
      align-self: end;
      border: 0;
      border-radius: 999px;
      padding: 14px 20px;
      background: var(--ink);
      color: #fff;
      font: inherit;
      cursor: pointer;
    }}
    @keyframes rise {{
      from {{ transform: translateY(8px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}
    @media (max-width: 700px) {{
      body {{ padding: 0; }}
      main {{
        width: 100vw;
        height: 100vh;
        border-radius: 0;
      }}
      form {{
        grid-template-columns: 1fr;
      }}
      button {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <p>Chat JID: {chat_jid} · <a href="/ops">Open Ops Dashboard</a></p>
    </header>
    <section id="messages"></section>
    <div id="typing"></div>
    <form id="composer">
      <textarea id="input" placeholder="Type a message..." required></textarea>
      <button type="submit">Send</button>
    </form>
  </main>
  <script>
    const messagesEl = document.getElementById("messages");
    const typingEl = document.getElementById("typing");
    const formEl = document.getElementById("composer");
    const inputEl = document.getElementById("input");
    let since = 0;

    function renderMessage(item) {{
      const wrapper = document.createElement("article");
      wrapper.className = `message ${{item.role}}`;
      const text = document.createElement("div");
      text.textContent = item.text;
      const meta = document.createElement("div");
      meta.className = "meta";
      const author = item.author ? `${{item.author}} • ` : "";
      meta.textContent = author + new Date(item.timestamp).toLocaleTimeString();
      wrapper.append(text, meta);
      messagesEl.appendChild(wrapper);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }}

    async function poll() {{
      const response = await fetch(`/api/messages?since=${{since}}`, {{ cache: "no-store" }});
      if (!response.ok) return;
      const data = await response.json();
      for (const item of data.messages) renderMessage(item);
      since = data.next_since;
      typingEl.textContent = data.typing ? "Assistant is thinking..." : "";
    }}

    async function send(text) {{
      const response = await fetch("/api/send", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ text }})
      }});
      if (!response.ok) {{
        const body = await response.text();
        throw new Error(body || `HTTP ${{response.status}}`);
      }}
    }}

    formEl.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const text = inputEl.value.trim();
      if (!text) return;
      inputEl.value = "";
      try {{
        await send(text);
        await poll();
      }} catch (error) {{
        inputEl.value = text;
        alert(String(error));
      }}
    }});

    setInterval(() => {{
      poll().catch(() => undefined);
    }}, 1000);

    poll().catch(() => undefined);
  </script>
</body>
</html>
"""

    def _render_ops_page(self) -> str:
        title = escape(self._chat_name)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} Ops</title>
  <style>
    :root {{
      --bg: #f3f0ea;
      --panel: rgba(255, 255, 255, 0.9);
      --ink: #1c1917;
      --muted: #6b635c;
      --accent: #1f6f78;
      --border: rgba(28, 25, 23, 0.12);
      --good: #1f8a4d;
      --warn: #b26b00;
      --bad: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      padding: 24px;
      color: var(--ink);
      font-family: "Iowan Old Style", Georgia, serif;
      background:
        radial-gradient(circle at top right, rgba(31, 111, 120, 0.18), transparent 30%),
        linear-gradient(160deg, #ece5db, #f9f8f4 55%, #e9f1ef);
    }}
    header {{
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 40px);
    }}
    header p {{
      margin: 8px 0 0;
      color: var(--muted);
    }}
    a {{ color: var(--accent); }}
    .toolbar {{
      display: flex;
      gap: 12px;
      margin: 14px 0 18px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .toolbar input {{
      min-width: min(420px, 100%);
      padding: 12px 14px;
      border-radius: 999px;
      border: 1px solid var(--border);
      font: inherit;
      background: rgba(255,255,255,0.82);
    }}
    .toolbar button {{
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      background: var(--ink);
      color: white;
      font: inherit;
      cursor: pointer;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    .card {{
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px 18px;
      background: var(--panel);
      backdrop-filter: blur(10px);
      box-shadow: 0 18px 40px rgba(30, 41, 59, 0.08);
    }}
    .wide {{
      grid-column: 1 / -1;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .kpi {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255,255,255,0.7);
    }}
    .kpi strong {{
      display: block;
      font-size: 24px;
      margin-top: 6px;
    }}
    ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}
    li {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.7);
    }}
    code {{
      font-family: "SFMono-Regular", Menlo, monospace;
      font-size: 12px;
    }}
    .status-good {{ color: var(--good); }}
    .status-warn {{ color: var(--warn); }}
    .status-bad {{ color: var(--bad); }}
    .empty {{ color: var(--muted); }}
    @media (max-width: 800px) {{
      body {{ padding: 16px; }}
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title} Ops</h1>
    <p><a href="/">Back to chat</a> · Auto-refresh every second.</p>
  </header>
  <div class="toolbar">
    <input id="filter" placeholder="Filter by jid, folder, task id, event, or text" />
    <button id="clear-filter" type="button">Clear</button>
  </div>
  <section class="grid">
    <article class="card wide">
      <h2>Overview</h2>
      <div class="kpis" id="kpis"></div>
    </article>
    <article class="card">
      <h2>Channels</h2>
      <ul id="channels"></ul>
    </article>
    <article class="card">
      <h2>Active Agents</h2>
      <ul id="queues"></ul>
    </article>
    <article class="card wide">
      <h2>Recent Agent Runs</h2>
      <ul id="agent-runs"></ul>
    </article>
    <article class="card wide">
      <h2>Selected Run Detail</h2>
      <div id="run-detail" class="empty">Select a recent agent run to inspect it.</div>
    </article>
    <article class="card wide">
      <h2>Registered Groups</h2>
      <ul id="groups"></ul>
    </article>
    <article class="card wide">
      <h2>Scheduled Tasks</h2>
      <ul id="tasks"></ul>
    </article>
    <article class="card">
      <h2>Sessions</h2>
      <ul id="sessions"></ul>
    </article>
    <article class="card">
      <h2>Recent Task Runs</h2>
      <ul id="task-runs"></ul>
    </article>
    <article class="card wide">
      <h2>Recent Messages</h2>
      <ul id="messages-log"></ul>
    </article>
    <article class="card wide">
      <h2>Recent Events</h2>
      <ul id="events"></ul>
    </article>
    <article class="card wide">
      <h2>Trace Timeline</h2>
      <ul id="timeline"></ul>
    </article>
  </section>
  <script>
    function statusClass(value) {{
      if (value === true || value === "success" || value === "completed" || value === "active") return "status-good";
      if (value === false || value === "error" || value === "failed") return "status-bad";
      return "status-warn";
    }}

    function fillList(id, items, renderItem) {{
      const el = document.getElementById(id);
      el.innerHTML = "";
      if (!items.length) {{
        const li = document.createElement("li");
        li.className = "empty";
        li.textContent = "No data";
        el.appendChild(li);
        return;
      }}
      for (const item of items) {{
        const li = document.createElement("li");
        li.innerHTML = renderItem(item);
        el.appendChild(li);
      }}
    }}

    function renderKpis(snapshot) {{
      const activeAgents = snapshot.queues.filter((item) => item.pid && item.returncode === null).length;
      const queued = snapshot.queues.reduce((sum, item) => sum + item.queue_size, 0);
      const cards = [
        ["Channels", snapshot.channels.length],
        ["Registered Groups", snapshot.registered_groups.length],
        ["Active Agents", activeAgents],
        ["Queued Items", queued],
        ["Agent Runs", snapshot.agent_runs.length],
      ];
      const el = document.getElementById("kpis");
      el.innerHTML = cards.map(([label, value]) => `<div class="kpi">${{label}}<strong>${{value}}</strong></div>`).join("");
    }}

    const filterEl = document.getElementById("filter");
    const clearFilterEl = document.getElementById("clear-filter");
    const runDetailEl = document.getElementById("run-detail");
    let currentFilter = "";
    let selectedRunId = "";

    function updateUrl() {{
      const url = new URL(window.location.href);
      if (currentFilter) {{
        url.searchParams.set("q", currentFilter);
      }} else {{
        url.searchParams.delete("q");
      }}
      if (selectedRunId) {{
        url.searchParams.set("run", selectedRunId);
      }} else {{
        url.searchParams.delete("run");
      }}
      history.replaceState(null, "", url);
    }}

    function scheduleRefresh(pushState = false) {{
      currentFilter = filterEl.value.trim();
      if (pushState) updateUrl();
      refresh().catch(() => undefined);
    }}

    async function refresh() {{
      const params = new URLSearchParams();
      if (currentFilter) params.set("q", currentFilter);
      if (selectedRunId) params.set("run", selectedRunId);
      const response = await fetch(`/api/ops?${{params.toString()}}`, {{ cache: "no-store" }});
      if (!response.ok) return;
      const snapshot = await response.json();
      renderKpis(snapshot);
      if (filterEl.value !== snapshot.filter) filterEl.value = snapshot.filter;
      selectedRunId = snapshot.selected_run_id || "";

      fillList("channels", snapshot.channels, (item) =>
        `<strong>${{item.name}}</strong> <span class="${{statusClass(item.connected)}}">${{item.connected ? "connected" : "down"}}</span><br><code>${{item.jid || "n/a"}}</code>`
      );
      fillList("queues", snapshot.queues, (item) =>
        `<strong><code>${{item.jid}}</code></strong><br>queue=${{item.queue_size}} · running=${{item.running}} · pid=${{item.pid || "n/a"}}<br><code>${{item.subprocess_name || "idle"}}</code>`
      );
      fillList("agent-runs", snapshot.agent_runs, (item) =>
        `<button type="button" data-run-id="${{item.run_id}}" class="select-run">${{item.run_id === selectedRunId ? "Selected" : "Inspect"}}</button><br><strong><code>${{item.kind}}</code></strong> <span class="${{statusClass(item.status)}}">${{item.status}}</span><br><code>${{item.jid}}</code> · folder=<code>${{item.group_folder}}</code> · ${{item.duration_ms}}ms<br>prompt=${{item.prompt_preview || "n/a"}}<br>reply=${{item.reply_preview || "n/a"}}${{item.error ? `<br>error=${{item.error}}` : ""}}`
      );
      const detail = snapshot.selected_agent_run;
      runDetailEl.className = detail ? "" : "empty";
      runDetailEl.innerHTML = detail
        ? `<p><strong>Run:</strong> <code>${{detail.run_id}}</code></p>
           <p><strong>Kind:</strong> ${{detail.kind}} · <strong>Status:</strong> <span class="${{statusClass(detail.status)}}">${{detail.status}}</span></p>
           <p><strong>Trace:</strong> <code>${{detail.trace_id || "n/a"}}</code></p>
           <p><strong>JID:</strong> <code>${{detail.jid}}</code> · <strong>Folder:</strong> <code>${{detail.group_folder}}</code></p>
           <p><strong>Started:</strong> ${{detail.started_at}} · <strong>Completed:</strong> ${{detail.completed_at}} · <strong>Duration:</strong> ${{detail.duration_ms}}ms</p>
           <p><strong>Prompt</strong></p>
           <pre><code>${{detail.prompt_full || detail.prompt_preview || "n/a"}}</code></pre>
           <p><strong>Reply</strong></p>
           <pre><code>${{detail.reply_full || detail.reply_preview || "n/a"}}</code></pre>
           ${{detail.error ? `<p><strong>Error:</strong> ${{detail.error}}</p>` : ""}}`
        : "Select a recent agent run to inspect it.";
      fillList("groups", snapshot.registered_groups, (item) =>
        `<strong>${{item.name}}</strong> <span class="${{statusClass(item.is_main ? "active" : "idle")}}">${{item.is_main ? "main" : "group"}}</span><br><code>${{item.jid}}</code> · folder=<code>${{item.folder}}</code><br>trigger=<code>${{item.trigger}}</code> · requires_trigger=${{item.requires_trigger !== false}}`
      );
      fillList("tasks", snapshot.scheduled_tasks, (item) =>
        `<strong><code>${{item.id}}</code></strong> <span class="${{statusClass(item.status)}}">${{item.status}}</span><br><code>${{item.chat_jid}}</code> · ${{item.schedule_type}}=${{item.schedule_value}}<br>next=${{item.next_run || "n/a"}}`
      );
      fillList("sessions", snapshot.sessions, (item) =>
        `<strong><code>${{item.group_folder}}</code></strong><br><code>${{item.session_id}}</code><br>${{item.updated_at}}`
      );
      fillList("task-runs", snapshot.task_runs, (item) =>
        `<strong><code>${{item.task_id}}</code></strong> <span class="${{statusClass(item.status)}}">${{item.status}}</span><br>${{item.run_at}} · ${{item.duration_ms}}ms${{item.error ? `<br>${{item.error}}` : ""}}`
      );
      fillList("messages-log", snapshot.recent_messages, (item) =>
        `<strong><code>${{item.chat_jid}}</code></strong><br>${{item.sender}} · ${{item.timestamp}}<br>${{item.content}}`
      );
      fillList("events", snapshot.recent_events, (item) =>
        `<strong>${{item.event || "event"}}</strong> <span class="${{statusClass(item.level)}}">${{item.level || "info"}}</span><br>${{item.timestamp || ""}} · <code>${{item.logger || "secnano"}}</code><br><code>${{JSON.stringify(item.fields || {{}})}}</code>`
      );
      fillList("timeline", snapshot.trace_timeline || [], (item) =>
        `<strong>${{item.kind}}</strong> · ${{item.timestamp || ""}}<br>${{item.title || ""}}<br>${{item.summary || ""}}<br><code>${{JSON.stringify(item.fields || {{}})}}</code>`
      );

      document.querySelectorAll(".select-run").forEach((button) => {{
        button.addEventListener("click", () => {{
          const next = button.getAttribute("data-run-id") || "";
          selectedRunId = next === selectedRunId ? "" : next;
          updateUrl();
          refresh().catch(() => undefined);
        }});
      }});
    }}

    filterEl.addEventListener("input", () => {{
      scheduleRefresh(true);
    }});
    clearFilterEl.addEventListener("click", () => {{
      filterEl.value = "";
      scheduleRefresh(true);
    }});

    const searchParams = new URLSearchParams(window.location.search);
    currentFilter = searchParams.get("q") || "";
    selectedRunId = searchParams.get("run") || "";
    filterEl.value = currentFilter;

    setInterval(() => {{
      refresh().catch(() => undefined);
    }}, 1000);

    refresh().catch(() => undefined);
  </script>
</body>
</html>
"""

    def _ops_payload(
        self,
        filter_text: str | None = None,
        selected_run_id: str | None = None,
    ) -> dict[str, Any]:
        if self._ops_snapshot is None:
            return {
                "enabled": False,
                "filter": filter_text or "",
                "selected_run_id": selected_run_id or "",
            }
        payload = self._ops_snapshot(filter_text, selected_run_id)
        payload.setdefault("filter", filter_text or "")
        payload.setdefault("selected_run_id", selected_run_id or "")
        payload["enabled"] = True
        return payload

    def _make_handler(self):
        channel = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(int(status))
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_text(self, status: HTTPStatus, body: str, content_type: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(int(status))
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._send_text(HTTPStatus.OK, channel._render_page(), "text/html")
                    return
                if parsed.path == "/ops":
                    self._send_text(HTTPStatus.OK, channel._render_ops_page(), "text/html")
                    return
                if parsed.path == "/api/messages":
                    params = parse_qs(parsed.query)
                    try:
                        since = int((params.get("since") or ["0"])[0])
                    except ValueError:
                        since = 0
                    self._send_json(HTTPStatus.OK, channel._messages_since(since))
                    return
                if parsed.path == "/api/ops":
                    params = parse_qs(parsed.query)
                    filter_text = (params.get("q") or [""])[0]
                    selected_run_id = (params.get("run") or [""])[0]
                    self._send_json(
                        HTTPStatus.OK,
                        channel._ops_payload(filter_text, selected_run_id),
                    )
                    return
                if parsed.path == "/healthz":
                    self._send_json(HTTPStatus.OK, {"ok": True, "jid": channel._chat_jid})
                    return
                self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain")

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != "/api/send":
                    self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain")
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    content_length = 0
                body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self._send_text(HTTPStatus.BAD_REQUEST, "Invalid JSON body", "text/plain")
                    return

                text = str(data.get("text", "")).strip()
                if not text:
                    self._send_text(HTTPStatus.BAD_REQUEST, "Message text is required", "text/plain")
                    return

                try:
                    channel._dispatch_inbound_message(text)
                except Exception as exc:
                    log.error("Failed to dispatch inbound web message", error=str(exc))
                    self._send_text(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "Failed to dispatch message",
                        "text/plain",
                    )
                    return

                self._send_json(HTTPStatus.ACCEPTED, {"accepted": True})

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

        return Handler

    def _serve(self) -> None:
        try:
            self._httpd = ThreadingHTTPServer((self._host, self._port), self._make_handler())
            self._server_ready.set()
            self._httpd.serve_forever(poll_interval=0.2)
        except Exception as exc:
            self._startup_error = exc
            self._server_ready.set()
        finally:
            if self._httpd is not None:
                self._httpd.server_close()

    async def connect(self) -> None:
        if self.is_connected():
            return

        self._loop = asyncio.get_running_loop()
        self._startup_error = None
        self._server_ready.clear()
        self._thread = threading.Thread(target=self._serve, name="secnano-web-channel", daemon=True)
        self._thread.start()
        await asyncio.to_thread(self._server_ready.wait, 5.0)
        if self._startup_error is not None:
            raise RuntimeError(f"Failed to start web channel: {self._startup_error}")

        self._seed_history()
        await self._on_chat_metadata(
            ChatMetadata(
                chat_jid=self._chat_jid,
                timestamp=_now_utc(),
                name=self._chat_name,
                channel=self.name,
                is_group=True,
            )
        )
        log.info("Web channel listening", url=self.url, jid=self._chat_jid)

    async def send_message(self, jid: str, text: str) -> None:
        if not self.owns_jid(jid):
            raise ValueError(f"Web channel does not own JID {jid!r}")
        self._append_message("assistant", text)

    def is_connected(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._httpd is not None

    def owns_jid(self, jid: str) -> bool:
        return jid == self._chat_jid

    async def disconnect(self) -> None:
        if self._httpd is not None:
            httpd = self._httpd
            self._httpd = None
            await asyncio.to_thread(httpd.shutdown)
        if self._thread is not None:
            thread = self._thread
            self._thread = None
            await asyncio.to_thread(thread.join, 5.0)

    async def set_typing(self, jid: str, is_typing: bool) -> None:
        if self.owns_jid(jid):
            with self._messages_lock:
                self._typing = is_typing
