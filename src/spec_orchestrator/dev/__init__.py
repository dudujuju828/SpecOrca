"""Backwards-compatibility shim: spec_orchestrator.dev → spec_orca.dev."""

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.dev' instead of 'spec_orchestrator.dev'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)
