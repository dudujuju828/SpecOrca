"""Command-line interface for SpecOrca."""

from __future__ import annotations

import argparse
import shutil
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from spec_orca import __version__

if TYPE_CHECKING:
    from spec_orca.orchestrator import ExecutionSummary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-orca",
        description="SpecOrca — a spec-driven two-role orchestrator (Architect / Agent).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the orchestration loop.")
    run_parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Path to the YAML spec file.",
    )
    run_parser.add_argument(
        "--max-steps",
        type=int,
        default=1,
        help="Maximum number of orchestration steps (default: 1).",
    )
    run_parser.add_argument(
        "--backend",
        type=str,
        default=None,
        choices=["claude", "mock"],
        help=(
            "Backend to use for execution. Overrides the SPEC_ORCA_BACKEND env var. Default: mock."
        ),
    )
    run_parser.add_argument(
        "--goal",
        type=str,
        default=None,
        help="Override the goal from the spec file.",
    )
    run_parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="Path to write a state snapshot JSON file.",
    )
    stop_group = run_parser.add_mutually_exclusive_group()
    stop_group.add_argument(
        "--stop-on-failure",
        dest="stop_on_failure",
        action="store_true",
        default=True,
        help="Stop the run on the first failed spec (default).",
    )
    stop_group.add_argument(
        "--continue-on-failure",
        dest="stop_on_failure",
        action="store_false",
        help="Continue executing specs even if a failure occurs.",
    )
    run_parser.add_argument(
        "--auto-commit",
        action="store_true",
        default=False,
        help=(
            "Automatically commit changes after a successful run. "
            "Off by default. Only tracked files are staged."
        ),
    )
    run_parser.add_argument(
        "--commit-prefix",
        type=str,
        default=None,
        help=(
            "Conventional Commit prefix for auto-commit messages "
            "(e.g. 'feat', 'chore', 'test'). Ignored unless --auto-commit is set."
        ),
    )

    plan_parser = subparsers.add_parser("plan", help="Validate and print the spec plan.")
    plan_parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Path to the YAML spec file.",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Check environment health.")
    doctor_parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="Optional spec file path to validate readability.",
    )
    doctor_parser.add_argument(
        "--backend",
        type=str,
        default=None,
        choices=["claude", "mock"],
        help="Optional backend to validate (defaults to env/default selection).",
    )

    return parser


def _run_command(
    spec_path: Path,
    max_steps: int,
    backend_name: str | None,
    *,
    goal_override: str | None,
    state_path: Path | None,
    stop_on_failure: bool,
    auto_commit: bool,
    commit_prefix: str | None,
) -> int:
    """Execute the 'run' subcommand."""
    from spec_orca.agent import Agent
    from spec_orca.architect import SimpleArchitect
    from spec_orca.backends import (
        ClaudeCodeNotFoundError,
        create_backend,
        resolve_backend_name,
    )
    from spec_orca.models import Context
    from spec_orca.orchestrator import Orchestrator
    from spec_orca.spec import SpecValidationError
    from spec_orca.state import ProjectState, build_state, save_state

    try:
        architect = SimpleArchitect(spec_path)
    except (FileNotFoundError, SpecValidationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        name = resolve_backend_name(backend_name)
        backend = create_backend(name)
    except (ValueError, ClaudeCodeNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    goal = goal_override or architect.goal or "unspecified"
    context = Context(
        repo_path=Path.cwd(),
        spec_path=spec_path.resolve(),
        goal=goal,
        backend_name=name,
    )
    agent = Agent(backend)
    orchestrator = Orchestrator(architect, agent, context)
    summary = orchestrator.run(max_steps=max_steps, stop_on_failure=stop_on_failure)

    _print_run_summary(summary)

    if state_path is not None:
        try:
            base_state = build_state(context.repo_path)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        state = ProjectState(
            repo_path=base_state.repo_path,
            git_head_sha=base_state.git_head_sha,
            tracked_files=base_state.tracked_files,
            status_summary=base_state.status_summary,
            diff_summary=base_state.diff_summary,
            last_test_summary=base_state.last_test_summary,
            history=list(summary.results),
        )
        save_state(state, state_path)

    # -- optional auto-commit -----------------------------------------------
    if auto_commit:
        from spec_orca.dev.git import GitError
        from spec_orca.dev.git import auto_commit as do_commit

        commit_msg = _commit_message(summary, goal)
        try:
            committed = do_commit(commit_msg, prefix=commit_prefix)
            if committed:
                print("Auto-commit created.")
            else:
                print("Auto-commit skipped (no changes).")
        except GitError as exc:
            print(f"Auto-commit failed: {exc}", file=sys.stderr)
            return 1

    return 0


def _plan_command(spec_path: Path) -> int:
    from spec_orca.architect import SimpleArchitect
    from spec_orca.spec import SpecValidationError

    try:
        architect = SimpleArchitect(spec_path)
    except (FileNotFoundError, SpecValidationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if architect.goal:
        print(f"Goal: {architect.goal}")
    print("Plan:")
    for index, spec in enumerate(architect.specs, start=1):
        deps = f" (deps: {', '.join(spec.dependencies)})" if spec.dependencies else ""
        print(f"{index}. {spec.id} - {spec.title}{deps}")
    return 0


def _doctor_command(spec_path: Path | None, backend_name: str | None) -> int:
    from spec_orca.backends import resolve_backend_name

    failures = 0
    checks: list[tuple[str, bool, str]] = []

    py_ok = sys.version_info >= (3, 11)
    checks.append(("python", py_ok, _format_python_version()))

    git_ok, git_detail = _check_git()
    checks.append(("git", git_ok, git_detail))

    if spec_path is None:
        checks.append(("spec", True, "skipped (no --spec provided)"))
    else:
        spec_ok, spec_detail = _check_spec_path(spec_path)
        checks.append(("spec", spec_ok, spec_detail))

    try:
        resolved_backend = resolve_backend_name(backend_name)
    except ValueError as exc:
        checks.append(("backend", False, str(exc)))
        resolved_backend = None

    if resolved_backend is None:
        pass
    elif resolved_backend == "mock":
        checks.append(("backend", True, "mock backend available"))
    else:
        backend_ok, backend_detail = _check_claude_executable()
        checks.append(("backend", backend_ok, backend_detail))

    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"{name}: {status} - {detail}")
        if not ok:
            failures += 1

    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        spec_path: Path = args.spec
        max_steps: int = args.max_steps
        backend_name: str | None = args.backend
        goal_override: str | None = args.goal
        state_path: Path | None = args.state
        stop_on_failure: bool = args.stop_on_failure
        ac: bool = args.auto_commit
        cp: str | None = args.commit_prefix
        return _run_command(
            spec_path,
            max_steps,
            backend_name,
            goal_override=goal_override,
            state_path=state_path,
            stop_on_failure=stop_on_failure,
            auto_commit=ac,
            commit_prefix=cp,
        )

    if args.command == "plan":
        plan_spec_path: Path = args.spec
        return _plan_command(plan_spec_path)

    if args.command == "doctor":
        doctor_spec_path: Path | None = args.spec
        doctor_backend_name: str | None = args.backend
        return _doctor_command(doctor_spec_path, doctor_backend_name)

    # No subcommand — print help by default.
    parser.print_help()
    return 0


def _print_run_summary(summary: ExecutionSummary) -> None:
    print("Progress:")
    if not summary.step_details:
        print("No steps executed.")
    else:
        rows = []
        for step in summary.step_details:
            rows.append(
                (
                    str(step.index),
                    step.spec_id,
                    step.result.status.value,
                    str(step.attempts),
                    _clean_summary(step.result.summary),
                )
            )
        _print_table(["Step", "Spec", "Status", "Attempts", "Summary"], rows)

    print(
        "Totals: "
        f"completed={summary.completed}, "
        f"failed={summary.failed}, "
        f"pending={summary.pending}, "
        f"in_progress={summary.in_progress}"
    )
    print(f"Stopped: {summary.stopped_reason}")


def _print_table(headers: Iterable[str], rows: Iterable[tuple[str, ...]]) -> None:
    rows_list = list(rows)
    widths = [len(header) for header in headers]
    for row in rows_list:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = "  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    print(header_line)
    print("-" * len(header_line))
    for row in rows_list:
        line = "  ".join(row[idx].ljust(widths[idx]) for idx in range(len(widths)))
        print(line)


def _clean_summary(summary: str) -> str:
    collapsed = " ".join(summary.split())
    return textwrap.shorten(collapsed, width=60, placeholder="...")


def _commit_message(summary: ExecutionSummary, goal: str) -> str:
    if summary.specs:
        return f"spec-orca run: {summary.specs[0].title}"
    return f"spec-orca run: {goal}"


def _check_git() -> tuple[bool, str]:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except OSError as exc:
        return False, f"git not available ({exc})"
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip() or "git command failed"
    return True, proc.stdout.strip()


def _check_spec_path(spec_path: Path) -> tuple[bool, str]:
    resolved = spec_path.resolve()
    if not resolved.exists():
        return False, f"spec not found: {resolved}"
    if not resolved.is_file():
        return False, f"spec path is not a file: {resolved}"
    try:
        resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"spec not readable: {exc}"
    return True, str(resolved)


def _check_claude_executable() -> tuple[bool, str]:
    executable = _resolve_claude_executable()
    if shutil.which(executable) is None:
        return (
            False,
            (
                f"Claude Code CLI not found: '{executable}'. "
                "Install it or set CLAUDE_CODE_EXECUTABLE."
            ),
        )
    return True, f"found {executable}"


def _resolve_claude_executable() -> str:
    value = _read_env_value("CLAUDE_CODE_EXECUTABLE")
    return value or "claude"


def _read_env_value(key: str) -> str | None:
    import os

    value = os.environ.get(key)
    if value is None:
        return None
    return value.strip() or None


def _format_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


if __name__ == "__main__":
    sys.exit(main())
