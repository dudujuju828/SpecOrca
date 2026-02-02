"""Command-line interface for spec-orchestrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spec_orchestrator import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-orchestrator",
        description="A spec-driven two-role orchestrator (Architect / Agent).",
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
        help="Path to the specification file (Markdown or YAML).",
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
            "Backend to use for execution. "
            "Overrides the SPEC_ORCHESTRATOR_BACKEND env var. "
            "Default: mock."
        ),
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

    return parser


def _run_command(
    spec_path: Path,
    max_steps: int,
    backend_name: str | None,
    *,
    auto_commit: bool,
    commit_prefix: str | None,
) -> int:
    """Execute the 'run' subcommand."""
    from spec_orchestrator.backends import (
        ClaudeCodeNotFoundError,
        create_backend,
        resolve_backend_name,
    )
    from spec_orchestrator.loader import load_spec
    from spec_orchestrator.orchestrator import run_loop
    from spec_orchestrator.stubs import SimpleArchitect

    try:
        spec = load_spec(spec_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        name = resolve_backend_name(backend_name)
        backend = create_backend(name)
    except (ValueError, ClaudeCodeNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    architect = SimpleArchitect()
    state = run_loop(spec=spec, architect=architect, backend=backend, max_steps=max_steps)

    for result in state.history:
        print(f"[step {result.step_index}] {result.status.value}: {result.output}")

    if state.done:
        print(f"Completed after {state.current_step} step(s).")
    else:
        print(f"Stopped at step {state.current_step} (max-steps reached).")

    # -- optional auto-commit -----------------------------------------------
    if auto_commit:
        from spec_orchestrator.dev.git import GitError
        from spec_orchestrator.dev.git import auto_commit as do_commit

        commit_msg = f"spec-orchestrator run: {spec.title}"
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        spec_path: Path = args.spec
        max_steps: int = args.max_steps
        backend_name: str | None = args.backend
        ac: bool = args.auto_commit
        cp: str | None = args.commit_prefix
        return _run_command(
            spec_path,
            max_steps,
            backend_name,
            auto_commit=ac,
            commit_prefix=cp,
        )

    # No subcommand — print help by default.
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
