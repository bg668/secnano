from __future__ import annotations

import argparse
import json
import sys

from src.v2.archive.writer import ArchiveWriter
from src.v2.liubu.backends.host import HostExecutionBackend
from src.v2.menxia.guard import OutputGuard
from src.v2.roles.loader import RoleLoadError, load_role_spec
from src.v2.schemas.archive import TaskArchiveRecord
from src.v2.schemas.reply import Rejection
from src.v2.tongzhengsi.cli_channel import build_inbound_event
from src.v2.tongzhengsi.errors import IngressError
from src.v2.zhongshu.orchestrator import orchestrate


def run_delegate(role: str, task: str) -> int:
    event = build_inbound_event(role=role, task=task)
    role_spec = load_role_spec(event.role)
    orchestration = orchestrate(event, role_spec=role_spec, backend=HostExecutionBackend())
    guarded = OutputGuard().inspect(orchestration.reply)

    record = TaskArchiveRecord(
        task_id=event.task_id,
        inbound=event,
        cognition=orchestration.cognition_result,
        execution=orchestration.execution_result,
        reply=orchestration.reply,
        guarded=guarded,
        error=guarded.reason if isinstance(guarded, Rejection) else None,
    )
    archive_path = ArchiveWriter().write(record)

    if isinstance(guarded, Rejection):
        print(f"rejected: {guarded.reason}", file=sys.stderr)
        print(f"archive: {archive_path}", file=sys.stderr)
        return 3

    print(guarded.content)
    return 0


def run_self_test_chain() -> int:
    exit_code = run_delegate(role="demo", task="run echo hello")
    if exit_code != 0:
        return exit_code
    print(json.dumps({"chain": "ok"}, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secnano_v2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    delegate = subparsers.add_parser("delegate")
    delegate.add_argument("--role", required=True)
    delegate.add_argument("--task", required=True)

    self_test = subparsers.add_parser("self-test")
    self_test.add_argument("--chain", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "delegate":
            return run_delegate(role=args.role, task=args.task)
        if args.command == "self-test":
            if args.chain:
                return run_self_test_chain()
            print("missing --chain", file=sys.stderr)
            return 2
        parser.error("unknown command")
    except (IngressError, RoleLoadError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
