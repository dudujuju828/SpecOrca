"""Backwards-compatibility shim for spec_orchestrator → spec_orca rename.

This module re-exports the spec_orca package under the old name for
backwards compatibility. A deprecation warning is issued once per process.

Migration:
    Replace imports of ``spec_orchestrator`` with ``spec_orca``.

This shim will be removed in a future release.
"""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "The 'spec_orchestrator' package has been renamed to 'spec_orca'. "
    "Please update your imports. This compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from spec_orca
from spec_orca import __version__
from spec_orca.backends import (
    ClaudeBackend,
    ClaudeCodeNotFoundError,
    MockBackend,
    create_backend,
    resolve_backend_name,
)
from spec_orca.loader import load_spec
from spec_orca.models import (
    Instruction,
    OrchestratorState,
    Spec,
    SpecFormat,
    StepResult,
    StepStatus,
)
from spec_orca.orchestrator import run_loop
from spec_orca.protocols import AgentBackendProtocol, ArchitectProtocol
from spec_orca.stubs import EchoBackend, SimpleArchitect

__all__ = [
    "AgentBackendProtocol",
    "ArchitectProtocol",
    "ClaudeBackend",
    "ClaudeCodeNotFoundError",
    "EchoBackend",
    "Instruction",
    "MockBackend",
    "OrchestratorState",
    "SimpleArchitect",
    "Spec",
    "SpecFormat",
    "StepResult",
    "StepStatus",
    "__version__",
    "create_backend",
    "load_spec",
    "resolve_backend_name",
    "run_loop",
]
