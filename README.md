# secnano

A Python AI agent orchestrator with subprocess isolation. This is a Python translation of the TypeScript project `nanoclaw`.

## Key Differences from nanoclaw

1. **Docker container isolation** → **Python `subprocess.Popen` subprocess** (no Docker required)
2. **Claude Code CLI executor** → **Self-implemented lightweight agent loop** (while True + tool_use/tool_result, calling Anthropic Python SDK directly)
3. **TypeScript/Node.js** → **Python 3.11+**

## Setup

```bash
pip install -e .
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

## Usage

```bash
secnano
```

## Project Structure

```
secnano/
├── secnano/
│   ├── main.py                   # Host process wiring and lifecycle
│   ├── ingress.py                # Message/chat metadata ingress
│   ├── control_plane.py          # IPC task handling
│   ├── runtime_orchestration.py  # Runtime execution orchestration
│   ├── task_scheduler.py         # Scheduled task polling and enqueueing
│   ├── group_queue.py            # Per-group execution queue
│   ├── subprocess_runner.py      # Agent subprocess launcher
│   ├── trace.py                  # Stable trace event storage
│   ├── ops_view.py               # Ops/debug snapshot shaping
│   ├── db.py                     # SQLite persistence
│   └── channels/
│       ├── registry.py           # Channel registration
│       └── web.py                # Local web channel
├── agent_runner/
│   ├── main.py                   # Agent subprocess entry point
│   └── tools.py                  # Agent tool implementations
├── tests/
└── data/                         # Runtime state (ignored except .gitkeep)
```

## Architecture

### Message Flow

1. A channel (e.g., WhatsApp, Telegram) receives a message
2. The message is stored in SQLite and enqueued via `GroupQueue`
3. `GroupQueue` launches a subprocess agent via `subprocess_runner.py`
4. The agent subprocess runs `agent_runner/main.py`, which implements the Anthropic tool-use loop
5. The agent writes output back via stdout markers
6. The orchestrator reads the output and sends it back through the channel

### Session Management

Conversation history is saved to JSON files at `data/sessions/{group_folder}/history.json`. Sessions are tracked in the SQLite `sessions` table.

### IPC Protocol

Follow-up messages are written as JSON files to `data/ipc/{group_folder}/input/`. A `_close` sentinel file signals the subprocess to exit.

## Environment Variables

See `.env.example` for all configuration options.

## Repository Hygiene

- Runtime state lives under `data/`, `groups/`, and `store/` and is intentionally ignored by Git.
- Upstream reference code is not vendored into this repository; keep this repo focused on the runnable Python implementation and tests.
