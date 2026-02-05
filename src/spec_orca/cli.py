"""Command-line interface for SpecOrca."""

from __future__ import annotations

import argparse
import shutil
import sys
import textwrap
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from spec_orca import __version__

if TYPE_CHECKING:
    from spec_orca.orchestrator import ExecutionSummary


@dataclass(frozen=True)
class _ClaudeResolved:
    claude_bin: str
    claude_allowed_tools: list[str] | None
    claude_disallowed_tools: list[str] | None
    claude_tools: list[str] | None
    claude_max_turns: int | None
    claude_max_budget_usd: float | None
    claude_timeout_seconds: int | None
    claude_no_session_persistence: bool | None


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
    _add_claude_args(run_parser)
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
    _add_claude_args(doctor_parser)

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
    claude_bin: str | None,
    claude_allowed_tools: list[str] | None,
    claude_disallowed_tools: list[str] | None,
    claude_tools: list[str] | None,
    claude_max_turns: int | None,
    claude_max_budget_usd: float | None,
    claude_timeout_seconds: int | None,
    claude_no_session_persistence: bool | None,
) -> int:
    """Execute the 'run' subcommand."""
    from spec_orca.agent import Agent
    from spec_orca.architect import SimpleArchitect
    from spec_orca.backends import (
        ClaudeCodeConfig,
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
        config = _load_config(Path.cwd())
        name = resolve_backend_name(backend_name)
        claude_resolved = _resolve_claude_config(
            config,
            claude_bin=claude_bin,
            claude_allowed_tools=claude_allowed_tools,
            claude_disallowed_tools=claude_disallowed_tools,
            claude_tools=claude_tools,
            claude_max_turns=claude_max_turns,
            claude_max_budget_usd=claude_max_budget_usd,
            claude_timeout_seconds=claude_timeout_seconds,
            claude_no_session_persistence=claude_no_session_persistence,
        )
        no_session = (
            claude_resolved.claude_no_session_persistence
            if claude_resolved.claude_no_session_persistence is not None
            else True
        )
        claude_config = ClaudeCodeConfig(
            executable=claude_resolved.claude_bin,
            allowed_tools=claude_resolved.claude_allowed_tools,
            disallowed_tools=claude_resolved.claude_disallowed_tools,
            tools=claude_resolved.claude_tools,
            max_turns=claude_resolved.claude_max_turns,
            max_budget_usd=claude_resolved.claude_max_budget_usd,
            no_session_persistence=no_session,
            timeout=claude_resolved.claude_timeout_seconds,
        )
        backend = create_backend(name, claude_config=claude_config)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    goal = goal_override or architect.goal or "unspecified"
    context = Context(
        repo_path=Path.cwd(),
        spec_path=spec_path.resolve(),
        goal=goal,
        backend_name=name,
    )
    def _progress(msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)

    agent = Agent(backend)
    orchestrator = Orchestrator(architect, agent, context)
    _progress(f"spec-orca: starting run ({max_steps} max step(s), backend={name})")
    summary = orchestrator.run(
        max_steps=max_steps, stop_on_failure=stop_on_failure, on_progress=_progress
    )

    _print_run_summary(summary)
    run_success = summary.failed == 0
    exit_code = 0 if run_success else 1

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
    if auto_commit and not run_success:
        print("Auto-commit skipped (run failed).")
    elif auto_commit:
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

    return exit_code


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


def _doctor_command(
    spec_path: Path | None,
    backend_name: str | None,
    *,
    claude_bin: str | None,
    claude_allowed_tools: list[str] | None,
    claude_disallowed_tools: list[str] | None,
    claude_tools: list[str] | None,
    claude_max_turns: int | None,
    claude_max_budget_usd: float | None,
    claude_timeout_seconds: int | None,
    claude_no_session_persistence: bool | None,
) -> int:
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
        config = _load_config(Path.cwd())
        resolved_backend = resolve_backend_name(backend_name)
    except ValueError as exc:
        checks.append(("backend", False, str(exc)))
        resolved_backend = None

    if resolved_backend is None:
        pass
    elif resolved_backend == "mock":
        checks.append(("backend", True, "mock backend available"))
    else:
        claude_resolved = _resolve_claude_config(
            config,
            claude_bin=claude_bin,
            claude_allowed_tools=claude_allowed_tools,
            claude_disallowed_tools=claude_disallowed_tools,
            claude_tools=claude_tools,
            claude_max_turns=claude_max_turns,
            claude_max_budget_usd=claude_max_budget_usd,
            claude_timeout_seconds=claude_timeout_seconds,
            claude_no_session_persistence=claude_no_session_persistence,
        )
        backend_ok, backend_detail = _check_claude_executable(claude_resolved.claude_bin)
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
            claude_bin=args.claude_bin,
            claude_allowed_tools=_flatten_list(args.claude_allowed_tools),
            claude_disallowed_tools=_flatten_list(args.claude_disallowed_tools),
            claude_tools=_flatten_list(args.claude_tools),
            claude_max_turns=args.claude_max_turns,
            claude_max_budget_usd=args.claude_max_budget_usd,
            claude_timeout_seconds=args.claude_timeout_seconds,
            claude_no_session_persistence=args.claude_no_session_persistence,
        )

    if args.command == "plan":
        plan_spec_path: Path = args.spec
        return _plan_command(plan_spec_path)

    if args.command == "doctor":
        doctor_spec_path: Path | None = args.spec
        doctor_backend_name: str | None = args.backend
        return _doctor_command(
            doctor_spec_path,
            doctor_backend_name,
            claude_bin=args.claude_bin,
            claude_allowed_tools=_flatten_list(args.claude_allowed_tools),
            claude_disallowed_tools=_flatten_list(args.claude_disallowed_tools),
            claude_tools=_flatten_list(args.claude_tools),
            claude_max_turns=args.claude_max_turns,
            claude_max_budget_usd=args.claude_max_budget_usd,
            claude_timeout_seconds=args.claude_timeout_seconds,
            claude_no_session_persistence=args.claude_no_session_persistence,
        )

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


def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _flatten_list(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    flattened: list[str] = []
    for value in values:
        flattened.extend(_parse_csv(value) or [])
    return flattened or None


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


def _check_claude_executable(executable: str) -> tuple[bool, str]:
    if shutil.which(executable) is None:
        return (
            False,
            (
                f"Claude Code CLI not found: '{executable}'. "
                "Install it or set CLAUDE_CODE_EXECUTABLE."
            ),
        )
    return True, f"found {executable}"


def _read_env_value(key: str) -> str | None:
    import os

    value = os.environ.get(key)
    if value is None:
        return None
    return value.strip() or None


def _add_claude_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--claude-bin",
        type=str,
        default=None,
        help="Claude Code executable path/name (overrides CLAUDE_CODE_EXECUTABLE).",
    )
    parser.add_argument(
        "--claude-allowed-tools",
        action="append",
        default=None,
        help="Allowed tool patterns for Claude Code (repeatable).",
    )
    parser.add_argument(
        "--claude-disallowed-tools",
        action="append",
        default=None,
        help="Disallowed tool patterns for Claude Code (repeatable).",
    )
    parser.add_argument(
        "--claude-tools",
        action="append",
        default=None,
        help="Explicit Claude Code tool list (repeatable).",
    )
    parser.add_argument(
        "--claude-max-turns",
        type=int,
        default=None,
        help="Maximum Claude Code turns.",
    )
    parser.add_argument(
        "--claude-max-budget-usd",
        type=float,
        default=None,
        help="Maximum Claude Code budget (USD).",
    )
    parser.add_argument(
        "--claude-timeout-seconds",
        type=int,
        default=None,
        help="Claude Code timeout in seconds.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--claude-no-session-persistence",
        dest="claude_no_session_persistence",
        action="store_true",
        help="Disable Claude Code session persistence (default).",
    )
    group.add_argument(
        "--claude-session-persistence",
        dest="claude_no_session_persistence",
        action="store_false",
        help="Allow Claude Code to persist sessions to disk.",
    )
    parser.set_defaults(claude_no_session_persistence=None)


def _load_config(cwd: Path) -> dict[str, object]:
    config_path = _read_env_value("SPEC_ORCA_CONFIG")
    if config_path:
        return _load_config_file(Path(config_path))
    spec_orca_toml = cwd / "spec-orca.toml"
    if spec_orca_toml.exists():
        return _load_config_file(spec_orca_toml)
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        return _load_pyproject(pyproject)
    return {}


def _load_config_file(path: Path) -> dict[str, object]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Failed to read config file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in config file: {path}") from exc
    if not isinstance(data, dict):
        return {}
    return data


def _load_pyproject(path: Path) -> dict[str, object]:
    data = _load_config_file(path)
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return {}
    spec_orca = tool.get("spec_orca")
    if not isinstance(spec_orca, dict):
        return {}
    return spec_orca


def _resolve_claude_config(
    config: dict[str, object],
    *,
    claude_bin: str | None = None,
    claude_allowed_tools: list[str] | None = None,
    claude_disallowed_tools: list[str] | None = None,
    claude_tools: list[str] | None = None,
    claude_max_turns: int | None = None,
    claude_max_budget_usd: float | None = None,
    claude_timeout_seconds: int | None = None,
    claude_no_session_persistence: bool | None = None,
) -> _ClaudeResolved:
    env = _resolve_env_claude_config()
    file_config = _resolve_file_claude_config(config)

    claude_bin_resolved = file_config.claude_bin or env.claude_bin
    claude_allowed_resolved = file_config.claude_allowed_tools or env.claude_allowed_tools
    claude_disallowed_resolved = file_config.claude_disallowed_tools or env.claude_disallowed_tools
    claude_tools_resolved = file_config.claude_tools or env.claude_tools
    claude_max_turns_resolved = file_config.claude_max_turns or env.claude_max_turns
    claude_max_budget_resolved = file_config.claude_max_budget_usd or env.claude_max_budget_usd
    claude_timeout_resolved = (
        file_config.claude_timeout_seconds
        if file_config.claude_timeout_seconds is not None
        else env.claude_timeout_seconds
    )
    claude_no_session_resolved = (
        file_config.claude_no_session_persistence
        if file_config.claude_no_session_persistence is not None
        else env.claude_no_session_persistence
    )

    if claude_bin is not None:
        claude_bin_resolved = claude_bin
    if claude_allowed_tools is not None:
        claude_allowed_resolved = claude_allowed_tools
    if claude_disallowed_tools is not None:
        claude_disallowed_resolved = claude_disallowed_tools
    if claude_tools is not None:
        claude_tools_resolved = claude_tools
    if claude_max_turns is not None:
        claude_max_turns_resolved = claude_max_turns
    if claude_max_budget_usd is not None:
        claude_max_budget_resolved = claude_max_budget_usd
    if claude_timeout_seconds is not None:
        claude_timeout_resolved = claude_timeout_seconds
    if claude_no_session_persistence is not None:
        claude_no_session_resolved = claude_no_session_persistence

    return _ClaudeResolved(
        claude_bin=claude_bin_resolved,
        claude_allowed_tools=claude_allowed_resolved,
        claude_disallowed_tools=claude_disallowed_resolved,
        claude_tools=claude_tools_resolved,
        claude_max_turns=claude_max_turns_resolved,
        claude_max_budget_usd=claude_max_budget_resolved,
        claude_timeout_seconds=claude_timeout_resolved,
        claude_no_session_persistence=claude_no_session_resolved,
    )


def _resolve_env_claude_config() -> _ClaudeResolved:
    claude_no_session = _env_bool("CLAUDE_CODE_NO_SESSION_PERSISTENCE")
    return _ClaudeResolved(
        claude_bin=_read_env_value("CLAUDE_CODE_EXECUTABLE") or "claude",
        claude_allowed_tools=_parse_csv(_read_env_value("CLAUDE_CODE_ALLOWED_TOOLS")),
        claude_disallowed_tools=_parse_csv(_read_env_value("CLAUDE_CODE_DISALLOWED_TOOLS")),
        claude_tools=_parse_csv(_read_env_value("CLAUDE_CODE_TOOLS")),
        claude_max_turns=_env_int("CLAUDE_CODE_MAX_TURNS"),
        claude_max_budget_usd=_env_float("CLAUDE_CODE_MAX_BUDGET_USD"),
        claude_timeout_seconds=_env_int("CLAUDE_CODE_TIMEOUT") or 300,
        claude_no_session_persistence=claude_no_session if claude_no_session is not None else True,
    )


def _resolve_file_claude_config(config: dict[str, object]) -> _ClaudeResolved:
    value = config.get("claude", config)
    if not isinstance(value, dict):
        return _ClaudeResolved(
            claude_bin="",
            claude_allowed_tools=None,
            claude_disallowed_tools=None,
            claude_tools=None,
            claude_max_turns=None,
            claude_max_budget_usd=None,
            claude_timeout_seconds=None,
            claude_no_session_persistence=None,
        )
    return _ClaudeResolved(
        claude_bin=_config_str(value.get("claude_bin")) or "",
        claude_allowed_tools=_config_list(value.get("claude_allowed_tools")),
        claude_disallowed_tools=_config_list(value.get("claude_disallowed_tools")),
        claude_tools=_config_list(value.get("claude_tools")),
        claude_max_turns=_config_int(value.get("claude_max_turns")),
        claude_max_budget_usd=_config_float(value.get("claude_max_budget_usd")),
        claude_timeout_seconds=_config_int(value.get("claude_timeout_seconds")),
        claude_no_session_persistence=_config_bool(value.get("claude_no_session_persistence")),
    )


def _config_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _config_list(value: object) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = [item.strip() for item in value if item.strip()]
        return items or None
    return None


def _config_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _config_float(value: object) -> float | None:
    return value if isinstance(value, (int, float)) else None


def _config_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _env_int(key: str) -> int | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_float(key: str) -> float | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_bool(key: str) -> bool | None:
    raw = _read_env_value(key)
    if raw is None:
        return None
    return raw.lower() in {"1", "true", "yes", "on"}


def _format_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


if __name__ == "__main__":
    sys.exit(main())
