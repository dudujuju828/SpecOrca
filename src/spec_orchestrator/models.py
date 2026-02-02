"""Backwards-compatibility shim: spec_orchestrator.models → spec_orca.models."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.models' instead of 'spec_orchestrator.models'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.models import (
    Context,
    Instruction,
    OrchestratorState,
    Result,
    ResultStatus,
    Spec,
    SpecFormat,
    SpecStatus,
    StepResult,
    StepStatus,
)

__all__ = [
    "Context",
    "Instruction",
    "OrchestratorState",
    "Result",
    "ResultStatus",
    "Spec",
    "SpecFormat",
    "SpecStatus",
    "StepResult",
    "StepStatus",
]
