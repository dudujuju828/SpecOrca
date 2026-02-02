"""Backwards-compatibility shim: spec_orchestrator.stubs → spec_orca.stubs."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.stubs' instead of 'spec_orchestrator.stubs'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.stubs import EchoBackend, SimpleArchitect

__all__ = ["EchoBackend", "SimpleArchitect"]
