"""Orchestration loop -- ties Architect, Agent Backend, and state together."""

from __future__ import annotations

from spec_orca.models import OrchestratorState, Spec
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
