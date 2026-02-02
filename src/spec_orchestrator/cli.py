"""Backwards-compatibility shim: spec_orchestrator.cli → spec_orca.cli."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.cli' instead of 'spec_orchestrator.cli'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.cli import build_parser, main

__all__ = ["build_parser", "main"]
