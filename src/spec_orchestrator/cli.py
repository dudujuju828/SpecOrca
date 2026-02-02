"""Command-line interface for spec-orchestrator."""

from __future__ import annotations

import argparse
import sys

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    _args = parser.parse_args(argv)
    # No subcommand yet — print help by default.
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
