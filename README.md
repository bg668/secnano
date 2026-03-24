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
├── pyproject.toml
├── .env.example
├── secnano/
│   ├── main.py              # Main orchestrator (entry point)
│   ├── config.py            # Configuration constants
│   ├── types.py             # Type definitions (dataclasses)
│   ├── db.py                # SQLite database operations
│   ├── logger.py            # Structured logging
│   ├── env.py               # Safe .env file reader
│   ├── group_folder.py      # Group folder path validation
│   ├── group_queue.py       # Per-group message queue with concurrency control
│   ├── router.py            # Message formatting/routing
│   ├── ipc.py               # IPC watcher (filesystem-based)
│   ├── task_scheduler.py    # Scheduled task execution
│   ├── timezone_utils.py    # Timezone conversion
│   ├── sender_allowlist.py  # Sender filtering
│   ├── subprocess_runner.py # subprocess.Popen agent spawner
│   └── channels/
│       └── registry.py      # Channel registration system
└── agent_runner/
    ├── main.py              # Agent subprocess entry point
    └── tools.py             # Tool implementations for the agent loop
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
