"""Backend protocol for executing specs."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from spec_orca.models import Context, Result, Spec

__all__ = ["Backend"]


@runtime_checkable
class Backend(Protocol):
    """Executable backend that can run a spec in a given context."""

    def execute(self, spec: Spec, context: Context) -> Result:
        """Execute a spec and return the result."""
        ...

    def chat(self, prompt: str, *, cwd: Path | None = None) -> str:
        """Send a conversational prompt and return the raw text response.

        Unlike ``execute()``, this skips structured output, JSON schemas,
        and spec-implementation framing.
        """
        ...
