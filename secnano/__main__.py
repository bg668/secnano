from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import TYPE_CHECKING

from . import __version__
from .ipc_watcher import watch_once
from .ipc_writer import build_task_request, write_task_file
from .paths import ProjectPaths
from .runtime_db import TASK_TERMINAL_STATUSES, create_task, get_task, init_db, list_tasks, list_pending_tasks

if TYPE_CHECKING:
    from .runtime_db import TaskRecord

IPC_POLL_INTERVAL = 1.0  # seconds


def build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser, argparse.ArgumentParser, argparse.ArgumentParser]:
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
    init_db(paths)

    if args.command == "tasks":
        if args.tasks_command == "submit":
            task = create_task(
                paths,
                role=args.role,
                task=args.task,
                namespace=args.namespace,
                max_retries=args.max_retries,
            )
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "show":
            task = get_task(paths, args.task_id)
            if task is None:
                print(f"task not found: {args.task_id}", file=sys.stderr)
                return 1
            _print_task(task, args.json)
            return 0

        if args.tasks_command == "list":
            tasks = list_tasks(paths, status=args.status, limit=args.limit)
            _print_task_list(tasks, args.json)
            return 0

        if args.tasks_command == "poll":
            deadline = time.monotonic() + args.timeout
            while True:
                task = get_task(paths, args.task_id)
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
            from .worker_pool import WorkerPool

            pool = WorkerPool(
                paths,
                max_workers=args.max_workers,
                task_timeout=args.task_timeout,
            )
            pool.start()
            print(
                f"WorkerPool started: max_workers={args.max_workers}, "
                f"task_timeout={args.task_timeout}s, namespace={args.namespace}",
                file=sys.stderr,
            )
            try:
                while True:
                    # Process IPC files
                    try:
                        watch_once(paths, namespace=args.namespace)
                    except Exception:
                        pass
                    # Scan pending tasks into pool
                    try:
                        pending = list_pending_tasks(paths, limit=args.max_workers * 2)
                        for task in pending:
                            pool.enqueue(task.task_id, task.payload)
                    except Exception:
                        pass
                    time.sleep(IPC_POLL_INTERVAL)
            except KeyboardInterrupt:
                print("\nShutting down WorkerPool...", file=sys.stderr)
                pool.stop()
            return 0

        if args.workers_command == "status":
            # Status is only meaningful when pool is running in-process;
            # here we show DB-level info instead
            pending = list_pending_tasks(paths, limit=100)
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
