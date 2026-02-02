"""Backwards-compatibility shim: spec_orchestrator.protocols → spec_orca.protocols."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.protocols' instead of 'spec_orchestrator.protocols'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.protocols import AgentBackendProtocol, ArchitectProtocol

__all__ = ["AgentBackendProtocol", "ArchitectProtocol"]
