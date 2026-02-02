"""Backwards-compatibility shim: spec_orchestrator.orchestrator → spec_orca.orchestrator."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.orchestrator' instead of 'spec_orchestrator.orchestrator'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.orchestrator import run_loop

__all__ = ["run_loop"]
