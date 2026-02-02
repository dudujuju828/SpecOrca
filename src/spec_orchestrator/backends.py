"""Backwards-compatibility shim: spec_orchestrator.backends → spec_orca.backends."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.backends' instead of 'spec_orchestrator.backends'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.backends import (
    ClaudeBackend,
    ClaudeCodeNotFoundError,
    MockBackend,
    create_backend,
    resolve_backend_name,
)

__all__ = [
    "ClaudeBackend",
    "ClaudeCodeNotFoundError",
    "MockBackend",
    "create_backend",
    "resolve_backend_name",
]
