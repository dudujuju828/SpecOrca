"""Orchestration loop -- ties Architect, Agent Backend, and state together."""

from __future__ import annotations

from dataclasses import dataclass

from spec_orca.agent import Agent
from spec_orca.architect import SimpleArchitect
from spec_orca.models import Context, OrchestratorState, Result, ResultStatus, Spec, SpecStatus
from spec_orca.protocols import AgentBackendProtocol, ArchitectProtocol


def run_loop(
    spec: Spec,
    architect: ArchitectProtocol,
    backend: AgentBackendProtocol,
    max_steps: int = 1,
) -> OrchestratorState:
    """Run the orchestration loop.

    Args:
        spec: The loaded specification.
        architect: The planning role.
        backend: The execution role.
        max_steps: Maximum number of iterations (default 1).

    Returns:
        The final OrchestratorState after the loop completes.
    """
    state = OrchestratorState(spec=spec, max_steps=max_steps)

    while state.current_step < state.max_steps and not state.done:
        instruction = architect.next_instruction(state)
        if instruction is None:
            state.done = True
            break

        result = backend.execute(instruction)
        state.history.append(result)
        state.current_step += 1

        if not architect.review_result(state, result):
            state.done = True

    return state


@dataclass(frozen=True)
class ExecutionSummary:
    """Summary of an orchestration run."""

    steps: int
    results: list[Result]
    specs: list[Spec]
    completed: int
    failed: int
    pending: int
    in_progress: int
    stopped_reason: str


class Orchestrator:
    """Spec-level orchestrator that coordinates Architect and Agent."""

    def __init__(self, architect: SimpleArchitect, agent: Agent, context: Context) -> None:
        self._architect = architect
        self._agent = agent
        self._context = context

    def run(self, max_steps: int = 1, *, stop_on_failure: bool = True) -> ExecutionSummary:
        results: list[Result] = []
        steps = 0
        stopped_reason = "no_runnable_specs"

        while steps < max_steps:
            runnable = self._architect.runnable_specs()
            if not runnable:
                stopped_reason = "no_runnable_specs"
                break

            spec = self._agent.select_next_spec(runnable)
            if spec is None:
                stopped_reason = "no_runnable_specs"
                break
            spec = self._architect.mark_in_progress(spec.id)
            result = self._agent.execute(spec, self._context)
            results.append(result)
            self._architect.record_result(spec.id, result)
            steps += 1

            if stop_on_failure and result.status != ResultStatus.SUCCESS:
                stopped_reason = "failure"
                break

        if steps >= max_steps:
            stopped_reason = "max_steps"

        specs_snapshot = self._architect.specs
        completed = sum(spec.status == SpecStatus.DONE for spec in specs_snapshot)
        failed = sum(spec.status == SpecStatus.FAILED for spec in specs_snapshot)
        pending = sum(spec.status == SpecStatus.PENDING for spec in specs_snapshot)
        in_progress = sum(spec.status == SpecStatus.IN_PROGRESS for spec in specs_snapshot)

        return ExecutionSummary(
            steps=steps,
            results=results,
            specs=specs_snapshot,
            completed=completed,
            failed=failed,
            pending=pending,
            in_progress=in_progress,
            stopped_reason=stopped_reason,
        )
