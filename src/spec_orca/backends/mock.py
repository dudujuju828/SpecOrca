"""Deterministic mock backend for testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import overload

from spec_orca.models import (
    Context,
    Instruction,
    Result,
    ResultStatus,
    Spec,
    StepResult,
    StepStatus,
)

__all__ = ["MockBackend", "MockBackendConfig"]


@dataclass(frozen=True)
class MockBackendConfig:
    """Configuration for deterministic mock responses."""

    status: ResultStatus = ResultStatus.SUCCESS
    summary: str | None = None
    details: str = ""
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    error: str | None = None


class MockBackend:
    """Mock backend that can be configured to succeed/fail deterministically."""

    def __init__(self, *, config: MockBackendConfig | None = None) -> None:
        self._config = config or MockBackendConfig()

    @overload
    def execute(self, instruction: Instruction) -> StepResult: ...

    @overload
    def execute(self, spec: Spec, context: Context) -> Result: ...

    def execute(self, *args: object, **kwargs: object) -> Result | StepResult:
        if args:
            first = args[0]
            if isinstance(first, Instruction):
                if len(args) != 1:
                    msg = "execute(instruction) accepts exactly one positional argument"
                    raise TypeError(msg)
                return self._execute_instruction(first)
            if isinstance(first, Spec):
                if len(args) < 2 or not isinstance(args[1], Context):
                    msg = "execute(spec, context) requires a Context as the second argument"
                    raise TypeError(msg)
                return self._execute_spec(first)
        if "spec" in kwargs and "context" in kwargs:
            spec = kwargs.get("spec")
            context = kwargs.get("context")
            if not isinstance(spec, Spec) or not isinstance(context, Context):
                msg = "execute(spec, context) requires a Spec and Context"
                raise TypeError(msg)
            return self._execute_spec(spec)
        msg = "execute() requires either (instruction) or (spec, context)"
        raise TypeError(msg)

    def _execute_instruction(self, instruction: Instruction) -> StepResult:
        step_status = _step_status_from_result(self._config.status)
        summary = self._config.summary or f"Mock execution of step {instruction.step_index}"
        output = f"[mock] executed: {instruction.prompt}"
        return StepResult(
            step_index=instruction.step_index,
            status=step_status,
            output=output,
            summary=summary,
            files_touched=tuple(self._config.files_changed),
            commands_run=tuple(self._config.commands_run),
        )

    def _execute_spec(self, spec: Spec) -> Result:
        summary = self._config.summary or f"Mock execution of spec '{spec.title}'"
        return Result(
            status=self._config.status,
            summary=summary,
            details=self._config.details,
            files_changed=list(self._config.files_changed),
            commands_run=list(self._config.commands_run),
            error=self._config.error,
        )


def _step_status_from_result(status: ResultStatus) -> StepStatus:
    if status == ResultStatus.SUCCESS:
        return StepStatus.SUCCESS
    if status == ResultStatus.ERROR:
        return StepStatus.ERROR
    return StepStatus.FAILURE
