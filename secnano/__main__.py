from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time
from typing import TYPE_CHECKING

from . import __version__
from .ipc_watcher import watch_once
from .ipc_writer import build_task_request, write_task_file
from .paths import ProjectPaths
from .runtime_db import (
    TASK_TERMINAL_STATUSES,
    create_task,
    create_task_id,
    get_run_logs,
    get_task,
    init_db,
    list_tasks,
    list_pending_tasks,
    mark_cancelled,
    mark_paused,
    mark_resumed,
)

if TYPE_CHECKING:
    from .runtime_db import TaskRecord

IPC_POLL_INTERVAL = 1.0  # seconds


def build_parser() -> tuple[
    argparse.ArgumentParser,
    argparse.ArgumentParser,
    argparse.ArgumentParser,
    argparse.ArgumentParser,
]:
    parser = argparse.ArgumentParser(prog="secnano")
    parser.add_argument("--version", action="store_true", help="show version")
    subparsers = parser.add_subparsers(dest="command")

    tasks_parser = subparsers.add_parser("tasks", help="task management")
    tasks_subparsers = tasks_parser.add_subparsers(dest="tasks_command")

    submit_parser = tasks_subparsers.add_parser("submit", help="submit new task")
    submit_parser.add_argument("--role", required=True)
    submit_parser.add_argument("--task", required=True)
    submit_parser.add_argument("--namespace", default="main")
    submit_parser.add_argument("--max-retries", type=int, default=0)
    submit_parser.add_argument("--json", action="store_true")

    show_parser = tasks_subparsers.add_parser("show", help="show task")
    show_parser.add_argument("task_id")
    show_parser.add_argument("--json", action="store_true")

    list_parser = tasks_subparsers.add_parser("list", help="list tasks")
    list_parser.add_argument("--status")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--json", action="store_true")

    poll_parser = tasks_subparsers.add_parser("poll", help="poll task status")
    poll_parser.add_argument("task_id")
    poll_parser.add_argument("--timeout", type=int, default=120)
    poll_parser.add_argument("--interval", type=float, default=1.0)
    poll_parser.add_argument("--json", action="store_true")

    pause_parser = tasks_subparsers.add_parser("pause", help="pause a task")
    pause_parser.add_argument("task_id")
    pause_parser.add_argument("--json", action="store_true")

    resume_parser = tasks_subparsers.add_parser("resume", help="resume a paused task")
    resume_parser.add_argument("task_id")
    resume_parser.add_argument("--json", action="store_true")

    cancel_parser = tasks_subparsers.add_parser("cancel", help="cancel a task")
    cancel_parser.add_argument("task_id")
    cancel_parser.add_argument("--json", action="store_true")

    retry_parser = tasks_subparsers.add_parser("retry", help="retry a task (creates new task_id)")
    retry_parser.add_argument("task_id")
    retry_parser.add_argument("--json", action="store_true")

    logs_parser = tasks_subparsers.add_parser("logs", help="show run logs for a task")
    logs_parser.add_argument("task_id")
    logs_parser.add_argument("--json", action="store_true")

    ipc_parser = subparsers.add_parser("ipc", help="ipc tools")
    ipc_subparsers = ipc_parser.add_subparsers(dest="ipc_command")

    write_task_parser = ipc_subparsers.add_parser("write-task", help="write ipc task json")
    write_task_parser.add_argument("--file")
    write_task_parser.add_argument("--role")
    write_task_parser.add_argument("--task")
    write_task_parser.add_argument("--namespace", default="main")
    write_task_parser.add_argument("--timeout-sec", type=int, default=120)
    write_task_parser.add_argument("--max-retries", type=int, default=0)
    write_task_parser.add_argument("--json", action="store_true")

    watch_parser = ipc_subparsers.add_parser("watch", help="process ipc task files once")
    watch_parser.add_argument("--namespace", default="main")
    watch_parser.add_argument("--json", action="store_true")

    # workers subcommand
    workers_parser = subparsers.add_parser("workers", help="worker pool management")
    workers_subparsers = workers_parser.add_subparsers(dest="workers_command")

    start_parser = workers_subparsers.add_parser("start", help="start worker pool (foreground)")
    start_parser.add_argument("--max-workers", type=int, default=4)
    start_parser.add_argument("--task-timeout", type=int, default=300)
    start_parser.add_argument("--namespace", default="main")

    status_parser = workers_subparsers.add_parser("status", help="show worker pool status")
    status_parser.add_argument("--json", action="store_true")

    workers_subparsers.add_parser("stop", help="send stop signal (noop in this implementation)")

    return parser, tasks_parser, ipc_parser, workers_parser


def _print_task(task: "TaskRecord", json_output: bool) -> None:
    payload = task.to_json_dict()
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return
    print(f"{payload['task_id']} {payload['status']} role={payload['role']}")


def _print_task_list(tasks: list["TaskRecord"], json_output: bool) -> None:
    payload = [task.to_json_dict() for task in tasks]
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return
    for item in payload:
        print(f"{item['task_id']} {item['status']} role={item['role']}")


def run(argv: list[str] | None = None) -> int:
    parser, tasks_parser, ipc_parser, workers_parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command not in ("tasks", "ipc", "workers"):
        parser.print_help()
        return 0

    paths = ProjectPaths.discover()
    asyncio.run(init_db(paths))

    if args.command == "tasks":
        if args.tasks_command == "submit":
            task = asyncio.run(
                create_task(
                    paths,
                    role=args.role,
                    task=args.task,
                    namespace=args.namespace,
                    max_retries=args.max_retries,
                )
            )
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "show":
            task = asyncio.run(get_task(paths, args.task_id))
            if task is None:
                print(f"task not found: {args.task_id}", file=sys.stderr)
                return 1
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "list":
            tasks = asyncio.run(list_tasks(paths, status=args.status, limit=args.limit))
            _print_task_list(tasks, args.json)
            return 0

        if args.tasks_command == "poll":
            deadline = time.monotonic() + args.timeout
            while True:
                task = asyncio.run(get_task(paths, args.task_id))
                if task is None:
                    print(f"task not found: {args.task_id}", file=sys.stderr)
                    return 1
                if task.status in TASK_TERMINAL_STATUSES:
                    _print_task(task, args.json)
                    return 0
                if time.monotonic() >= deadline:
                    _print_task(task, args.json)
                    return 124
                time.sleep(args.interval)

        if args.tasks_command == "pause":
            task = asyncio.run(get_task(paths, args.task_id))
            if task is None:
                print(f"task not found: {args.task_id}", file=sys.stderr)
                return 1
            asyncio.run(mark_paused(paths, args.task_id))
            task = asyncio.run(get_task(paths, args.task_id))
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "resume":
            task = asyncio.run(get_task(paths, args.task_id))
            if task is None:
                print(f"task not found: {args.task_id}", file=sys.stderr)
                return 1
            asyncio.run(mark_resumed(paths, args.task_id))
            task = asyncio.run(get_task(paths, args.task_id))
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "cancel":
            task = asyncio.run(get_task(paths, args.task_id))
            if task is None:
                print(f"task not found: {args.task_id}", file=sys.stderr)
                return 1
            asyncio.run(mark_cancelled(paths, args.task_id))
            task = asyncio.run(get_task(paths, args.task_id))
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "retry":
            original = asyncio.run(get_task(paths, args.task_id))
            if original is None:
                print(f"task not found: {args.task_id}", file=sys.stderr)
                return 1
            new_task = asyncio.run(
                create_task(
                    paths,
                    role=original.role,
                    task=original.payload.get("task", ""),
                    namespace=original.namespace,
                    max_retries=original.max_retries,
                )
            )
            _print_task(new_task, args.json)
            return 0

        if args.tasks_command == "logs":
            logs = asyncio.run(get_run_logs(paths, args.task_id))
            if args.json:
                print(json.dumps(logs, ensure_ascii=False))
            else:
                if not logs:
                    print(f"no run logs for {args.task_id}")
                for entry in logs:
                    print(
                        f"attempt={entry.get('attempt_no')} status={entry.get('status')} "
                        f"duration_ms={entry.get('duration_ms')} created_at={entry.get('created_at')}"
                    )
            return 0

        tasks_parser.print_help()
        return 0

    if args.command == "ipc":
        if args.ipc_command == "write-task":
            if args.file:
                file_path = pathlib.Path(args.file)
                if not file_path.is_absolute():
                    print("--file must be absolute path", file=sys.stderr)
                    return 2
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            else:
                if not args.role or not args.task:
                    print("ipc write-task requires --file or (--role and --task)", file=sys.stderr)
                    return 2
                payload = build_task_request(
                    role=args.role,
                    task=args.task,
                    namespace=args.namespace,
                    timeout_sec=args.timeout_sec,
                    max_retries=args.max_retries,
                )
            path = write_task_file(paths, payload)
            response = {"file": str(path), "task_id": payload.get("task_id"), "namespace": payload.get("namespace")}
            if args.json:
                print(json.dumps(response, ensure_ascii=False))
            else:
                print(f"{response['file']} task_id={response['task_id']}")
            return 0

        if args.ipc_command == "watch":
            results = watch_once(paths, namespace=args.namespace)
            if args.json:
                print(json.dumps(results, ensure_ascii=False))
            else:
                print(f"processed={sum(1 for r in results if r.get('processed'))} total={len(results)}")
            return 0

        ipc_parser.print_help()
        return 0

    if args.command == "workers":
        if args.workers_command == "start":
            from .ipc_watcher import IPCWatcher
            from .scheduler import Scheduler
            from .worker_pool import WorkerPool

            pool = WorkerPool(
                paths,
                max_workers=args.max_workers,
                task_timeout=args.task_timeout,
            )
            ipc_watcher = IPCWatcher(paths, namespace=args.namespace)
            scheduler = Scheduler(paths)

            pool.start()
            ipc_watcher.start()
            scheduler.start()
            print(
                f"Daemon started: max_workers={args.max_workers}, "
                f"task_timeout={args.task_timeout}s, namespace={args.namespace}",
                file=sys.stderr,
            )
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                print("\nShutting down...", file=sys.stderr)
                scheduler.stop()
                ipc_watcher.stop()
                pool.stop()
            return 0

        if args.workers_command == "status":
            pending = asyncio.run(list_pending_tasks(paths, limit=100))
            status = {
                "pending_count": len(pending),
                "pending_task_ids": [t.task_id for t in pending],
            }
            if args.json:
                print(json.dumps(status, ensure_ascii=False))
            else:
                print(f"pending={status['pending_count']}")
            return 0

        if args.workers_command == "stop":
            print("Stop signal noted. If workers start is running, press Ctrl+C to stop it.", file=sys.stderr)
            return 0

        workers_parser.print_help()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
