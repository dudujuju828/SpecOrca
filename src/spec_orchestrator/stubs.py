"""Stub implementations of Architect and Backend for testing and development."""

from __future__ import annotations

from spec_orchestrator.models import (
    Instruction,
    OrchestratorState,
    StepResult,
    StepStatus,
)


class SimpleArchitect:
    """Minimal Architect that emits one instruction per step from the spec."""

    def next_instruction(self, state: OrchestratorState) -> Instruction | None:
        if state.done or state.current_step >= state.max_steps:
            return None
        return Instruction(
            spec=state.spec,
            step_index=state.current_step,
            prompt=f"Step {state.current_step}: implement spec '{state.spec.title}'",
        )

    def review_result(self, state: OrchestratorState, result: StepResult) -> bool:
        """Continue only if the result was successful and max steps not reached."""
        if result.status != StepStatus.SUCCESS:
            return False
        return state.current_step < state.max_steps


class EchoBackend:
    """Stub backend that echoes the instruction back as a successful result."""

    def execute(self, instruction: Instruction) -> StepResult:
        return StepResult(
            step_index=instruction.step_index,
            status=StepStatus.SUCCESS,
            output=f"[echo] {instruction.prompt}",
        )
