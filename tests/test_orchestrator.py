"""Tests for the orchestration loop."""

from __future__ import annotations

from pathlib import Path

from spec_orchestrator.models import (
    Instruction,
    OrchestratorState,
    Spec,
    SpecFormat,
    StepResult,
)
from spec_orchestrator.orchestrator import run_loop
from spec_orchestrator.stubs import EchoBackend, SimpleArchitect


def _make_spec() -> Spec:
    return Spec(
        source=Path("/tmp/test.md"),
        format=SpecFormat.MARKDOWN,
        title="Test Spec",
        raw_content="# Test Spec\nContent.",
    )


class TestRunLoop:
    def test_single_step_default(self) -> None:
        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=EchoBackend(),
        )
        assert state.current_step == 1
        assert len(state.history) == 1

    def test_multi_step(self) -> None:
        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=EchoBackend(),
            max_steps=3,
        )
        assert state.current_step == 3
        assert len(state.history) == 3

    def test_history_step_indices(self) -> None:
        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=EchoBackend(),
            max_steps=3,
        )
        indices = [r.step_index for r in state.history]
        assert indices == [0, 1, 2]

    def test_stops_on_architect_none(self) -> None:
        """Architect that returns None after 2 steps."""

        class LimitedArchitect:
            def next_instruction(self, state: OrchestratorState) -> Instruction | None:
                if state.current_step >= 2:
                    return None
                return Instruction(spec=state.spec, step_index=state.current_step, prompt="go")

            def review_result(self, state: OrchestratorState, result: StepResult) -> bool:
                return True

        state = run_loop(
            spec=_make_spec(),
            architect=LimitedArchitect(),
            backend=EchoBackend(),
            max_steps=10,
        )
        assert state.current_step == 2
        assert state.done is True

    def test_stops_on_review_false(self) -> None:
        """Architect that stops after first review."""

        class OneAndDoneArchitect:
            def next_instruction(self, state: OrchestratorState) -> Instruction | None:
                return Instruction(spec=state.spec, step_index=state.current_step, prompt="go")

            def review_result(self, state: OrchestratorState, result: StepResult) -> bool:
                return False

        state = run_loop(
            spec=_make_spec(),
            architect=OneAndDoneArchitect(),
            backend=EchoBackend(),
            max_steps=10,
        )
        assert state.current_step == 1
        assert state.done is True

    def test_deterministic_with_stubs(self) -> None:
        """Same inputs produce identical state."""
        spec = _make_spec()

        state_a = run_loop(
            spec=spec, architect=SimpleArchitect(), backend=EchoBackend(), max_steps=3
        )
        state_b = run_loop(
            spec=spec, architect=SimpleArchitect(), backend=EchoBackend(), max_steps=3
        )

        assert state_a.current_step == state_b.current_step
        assert len(state_a.history) == len(state_b.history)
        for a, b in zip(state_a.history, state_b.history, strict=True):
            assert a.step_index == b.step_index
            assert a.status == b.status
            assert a.output == b.output
