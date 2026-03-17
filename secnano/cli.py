"""CLI entry for secnano."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from secnano import __version__
from secnano.audit_command import run_audit_list, run_audit_show
from secnano.bootstrap import run_bootstrap
from secnano.context import load_context
from secnano.delegate_command import run_delegate
from secnano.doctor import run_doctor
from secnano.roles_commands import (
    run_roles_ensure_defaults,
    run_roles_list,
    run_roles_promote_memory,
    run_roles_show,
)
from secnano.runtime_command import run_runtime_inspect, run_runtime_validate


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

    roles_parser = subparsers.add_parser("roles", help="角色资产管理")
    roles_subparsers = roles_parser.add_subparsers(dest="roles_command", required=True)

    roles_ensure = roles_subparsers.add_parser(
        "ensure-defaults", help="确保默认角色资产存在"
    )
    roles_ensure.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    roles_ensure.add_argument("--debug", action="store_true", help="输出调试日志")
    roles_ensure.set_defaults(handler=_handle_roles_ensure_defaults)

    roles_list = roles_subparsers.add_parser("list", help="列出可用角色")
    roles_list.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    roles_list.add_argument("--debug", action="store_true", help="输出调试日志")
    roles_list.set_defaults(handler=_handle_roles_list)

    roles_show = roles_subparsers.add_parser("show", help="查看角色资产详情")
    roles_show.add_argument("role_name", help="角色名称")
    roles_show.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    roles_show.add_argument("--debug", action="store_true", help="输出调试日志")
    roles_show.set_defaults(handler=_handle_roles_show)

    roles_promote_memory = roles_subparsers.add_parser(
        "promote-memory", help="将任务归档提升到角色 MEMORY"
    )
    roles_promote_memory.add_argument("role_name", help="角色名称")
    roles_promote_memory.add_argument("task_id", help="任务 ID")
    roles_promote_memory.add_argument(
        "--json", action="store_true", dest="as_json", help="输出 JSON"
    )
    roles_promote_memory.add_argument("--debug", action="store_true", help="输出调试日志")
    roles_promote_memory.set_defaults(handler=_handle_roles_promote_memory)

    delegate_parser = subparsers.add_parser("delegate", help="执行最小委派链路")
    delegate_parser.add_argument(
        "--backend",
        required=True,
        choices=["host", "pyclaw_container"],
        help="委派后端名称",
    )
    delegate_parser.add_argument("--role", required=True, help="角色名称")
    delegate_parser.add_argument("--task", required=True, help="任务描述")
    delegate_parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    delegate_parser.add_argument("--debug", action="store_true", help="输出调试日志")
    delegate_parser.set_defaults(handler=_handle_delegate)

    audit_parser = subparsers.add_parser("audit", help="归档审计查询")
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command", required=True)

    audit_list = audit_subparsers.add_parser("list", help="列出归档任务")
    audit_list.add_argument("--limit", type=int, default=20, help="最多返回条数")
    audit_list.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    audit_list.add_argument("--debug", action="store_true", help="输出调试日志")
    audit_list.set_defaults(handler=_handle_audit_list)

    audit_show = audit_subparsers.add_parser("show", help="查看单个归档任务")
    audit_show.add_argument("task_id", help="任务 ID")
    audit_show.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    audit_show.add_argument("--debug", action="store_true", help="输出调试日志")
    audit_show.set_defaults(handler=_handle_audit_show)

    runtime_parser = subparsers.add_parser("runtime", help="运行时检查")
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_command", required=True)

    runtime_inspect = runtime_subparsers.add_parser("inspect", help="查看运行时依赖状态")
    runtime_inspect.add_argument(
        "--json", action="store_true", dest="as_json", help="输出 JSON"
    )
    runtime_inspect.add_argument("--debug", action="store_true", help="输出调试日志")
    runtime_inspect.set_defaults(handler=_handle_runtime_inspect)

    runtime_validate = runtime_subparsers.add_parser("validate", help="校验运行时必需依赖")
    runtime_validate.add_argument(
        "--json", action="store_true", dest="as_json", help="输出 JSON"
    )
    runtime_validate.add_argument("--debug", action="store_true", help="输出调试日志")
    runtime_validate.set_defaults(handler=_handle_runtime_validate)

    return parser


def _handle_doctor(args: argparse.Namespace) -> int:
    return run_doctor(load_context(), as_json=args.as_json)


def _handle_bootstrap(args: argparse.Namespace) -> int:
    return run_bootstrap(load_context(), dry_run=args.dry_run, as_json=args.as_json)


def _handle_roles_ensure_defaults(args: argparse.Namespace) -> int:
    return run_roles_ensure_defaults(load_context(), as_json=args.as_json, debug=args.debug)


def _handle_roles_list(args: argparse.Namespace) -> int:
    return run_roles_list(load_context(), as_json=args.as_json, debug=args.debug)


def _handle_roles_show(args: argparse.Namespace) -> int:
    return run_roles_show(
        load_context(),
        role_name=args.role_name,
        as_json=args.as_json,
        debug=args.debug,
    )


def _handle_roles_promote_memory(args: argparse.Namespace) -> int:
    return run_roles_promote_memory(
        load_context(),
        role_name=args.role_name,
        task_id=args.task_id,
        as_json=args.as_json,
        debug=args.debug,
    )


def _handle_delegate(args: argparse.Namespace) -> int:
    return run_delegate(
        load_context(),
        backend_name=args.backend,
        role=args.role,
        task=args.task,
        as_json=args.as_json,
        debug=args.debug,
    )


def _handle_audit_list(args: argparse.Namespace) -> int:
    return run_audit_list(
        load_context(),
        limit=args.limit,
        as_json=args.as_json,
        debug=args.debug,
    )


def _handle_audit_show(args: argparse.Namespace) -> int:
    return run_audit_show(
        load_context(),
        task_id=args.task_id,
        as_json=args.as_json,
        debug=args.debug,
    )


def _handle_runtime_inspect(args: argparse.Namespace) -> int:
    return run_runtime_inspect(load_context(), as_json=args.as_json, debug=args.debug)


def _handle_runtime_validate(args: argparse.Namespace) -> int:
    return run_runtime_validate(load_context(), as_json=args.as_json, debug=args.debug)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
