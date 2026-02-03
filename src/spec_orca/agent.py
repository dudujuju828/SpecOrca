"""Agent implementation that executes specs with a backend."""

from __future__ import annotations

from collections.abc import Sequence

from spec_orca.backend import Backend
from spec_orca.models import Context, Result, Spec

__all__ = ["Agent"]


class Agent:
    """Agent that selects the next spec and executes it."""

    def __init__(self, backend: Backend) -> None:
        self._backend = backend

    def select_next_spec(self, specs: Sequence[Spec]) -> Spec | None:
        if not specs:
            return None
        return specs[0]

    def execute(self, spec: Spec, context: Context) -> Result:
        return self._backend.execute(spec, context)

    def run_next(self, specs: Sequence[Spec], context: Context) -> tuple[Spec, Result] | None:
        spec = self.select_next_spec(specs)
        if spec is None:
            return None
        return spec, self.execute(spec, context)
