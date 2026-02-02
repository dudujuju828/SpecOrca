"""Deprecated CLI entry point for backwards compatibility.

This module provides the old ``spec-orchestrator`` command that prints
a deprecation warning and forwards to the new ``spec-orca`` command.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Entry point for the deprecated spec-orchestrator command."""
    print(
        "WARNING: 'spec-orchestrator' has been renamed to 'spec-orca'. "
        "Please update your scripts. This command will be removed in a future release.",
        file=sys.stderr,
    )
    from spec_orca.cli import main as new_main

    return new_main()


if __name__ == "__main__":
    sys.exit(main())
