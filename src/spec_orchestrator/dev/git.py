"""Backwards-compatibility shim: spec_orchestrator.dev.git → spec_orca.dev.git."""
# ruff: noqa: E402

from __future__ import annotations

import warnings

warnings.warn(
    "Import from 'spec_orca.dev.git' instead of 'spec_orchestrator.dev.git'. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from spec_orca.dev.git import (
    GitError,
    auto_commit,
    has_changes,
    normalize_message,
)

__all__ = ["GitError", "auto_commit", "has_changes", "normalize_message"]
