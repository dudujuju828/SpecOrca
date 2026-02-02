"""Protocols (interfaces) for the Architect and Agent Backend roles."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from spec_orca.models import Instruction, OrchestratorState, StepResult


@runtime_checkable
class ArchitectProtocol(Protocol):
    """Interface for the Architect role.

    The Architect inspects the current orchestration state and produces
    the next Instruction, or signals completion by returning None.
    """

    def next_instruction(self, state: OrchestratorState) -> Instruction | None:
        """Produce the next instruction or None if the goal is met."""
        ...

    def review_result(self, state: OrchestratorState, result: StepResult) -> bool:
        """Review a step result. Return True if orchestration should continue."""
        ...


@runtime_checkable
class AgentBackendProtocol(Protocol):
    """Interface for the Agent's coding backend.

    Receives an Instruction and returns a structured StepResult.
    """

    def execute(self, instruction: Instruction) -> StepResult:
        """Execute an instruction and return the result."""
        ...
