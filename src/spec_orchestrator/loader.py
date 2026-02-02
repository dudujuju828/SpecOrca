"""Backwards-compatibility shim: spec_orchestrator.loader → spec_orca.loader."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.loader' instead of 'spec_orchestrator.loader'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.loader import load_spec

__all__ = ["load_spec"]
