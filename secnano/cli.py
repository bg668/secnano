"""CLI entry for secnano."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from secnano import __version__
from secnano.bootstrap import run_bootstrap
from secnano.context import load_context
from secnano.doctor import run_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secnano",
        description="secnano command line tools",
    )
    parser.add_argument("--version", action="version", version=f"secnano {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="检查 secnano 本地运行环境")
    doctor_parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    doctor_parser.set_defaults(handler=_handle_doctor)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="初始化 secnano 开发环境",
    )
    bootstrap_parser.add_argument(
        "--dry-run", action="store_true", help="仅展示将执行的步骤，不做实际修改"
    )
    bootstrap_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="输出 JSON"
    )
    bootstrap_parser.set_defaults(handler=_handle_bootstrap)

    return parser


def _handle_doctor(args: argparse.Namespace) -> int:
    return run_doctor(load_context(), as_json=args.as_json)


def _handle_bootstrap(args: argparse.Namespace) -> int:
    return run_bootstrap(load_context(), dry_run=args.dry_run, as_json=args.as_json)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))

