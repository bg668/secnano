from __future__ import annotations

import argparse
import json
import sys
import time

from . import __version__
from .paths import ProjectPaths
from .runtime_db import TASK_TERMINAL_STATUSES, create_task, get_task, init_db, list_tasks


def build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
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

    return parser, tasks_parser


def _print_task(task, json_output: bool) -> None:
    payload = task.to_json_dict()
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return
    print(f"{payload['task_id']} {payload['status']} role={payload['role']}")


def _print_task_list(tasks, json_output: bool) -> None:
    payload = [task.to_json_dict() for task in tasks]
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return
    for item in payload:
        print(f"{item['task_id']} {item['status']} role={item['role']}")


def run(argv: list[str] | None = None) -> int:
    parser, tasks_parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command != "tasks":
        parser.print_help()
        return 0

    paths = ProjectPaths.discover()
    init_db(paths)

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


if __name__ == "__main__":
    raise SystemExit(run())
