"""Tests for the orchestration loop."""

from __future__ import annotations

from pathlib import Path

from spec_orchestrator.models import (
    Instruction,
    OrchestratorState,
    Spec,
    SpecFormat,
    StepResult,
    StepStatus,
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


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestRunLoopHappyPath:
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

    def test_all_results_are_success(self) -> None:
        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=EchoBackend(),
            max_steps=3,
        )
        assert all(r.status == StepStatus.SUCCESS for r in state.history)

    def test_spec_propagated_to_state(self) -> None:
        spec = _make_spec()
        state = run_loop(spec=spec, architect=SimpleArchitect(), backend=EchoBackend())
        assert state.spec is spec


# ---------------------------------------------------------------------------
# Failure-path tests
# ---------------------------------------------------------------------------


class TestRunLoopFailurePaths:
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

    def test_backend_failure_stops_via_architect(self) -> None:
        """A backend that returns FAILURE; SimpleArchitect should stop."""

        class FailingBackend:
            def execute(self, instruction: Instruction) -> StepResult:
                return StepResult(
                    step_index=instruction.step_index,
                    status=StepStatus.FAILURE,
                    output="boom",
                )

        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=FailingBackend(),
            max_steps=5,
        )
        assert state.current_step == 1
        assert state.done is True
        assert state.history[0].status == StepStatus.FAILURE

    def test_backend_error_stops_via_architect(self) -> None:
        """A backend that returns ERROR; SimpleArchitect should stop."""

        class ErrorBackend:
            def execute(self, instruction: Instruction) -> StepResult:
                return StepResult(
                    step_index=instruction.step_index,
                    status=StepStatus.ERROR,
                    output="timeout",
                )

        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=ErrorBackend(),
            max_steps=5,
        )
        assert state.current_step == 1
        assert state.done is True
        assert state.history[0].status == StepStatus.ERROR

    def test_max_steps_reached_without_done(self) -> None:
        """Architect that always continues — loop stops only by max_steps.

        This exercises the branch where state.done stays False.
        """

        class AlwaysContinueArchitect:
            def next_instruction(self, state: OrchestratorState) -> Instruction | None:
                return Instruction(
                    spec=state.spec, step_index=state.current_step, prompt="keep going"
                )

            def review_result(self, state: OrchestratorState, result: StepResult) -> bool:
                return True  # never signals done

        state = run_loop(
            spec=_make_spec(),
            architect=AlwaysContinueArchitect(),
            backend=EchoBackend(),
            max_steps=3,
        )
        assert state.current_step == 3
        assert state.done is False  # stopped by max_steps, not by architect
        assert len(state.history) == 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestRunLoopEdgeCases:
    def test_zero_max_steps(self) -> None:
        """max_steps=0 should produce no iterations."""
        state = run_loop(
            spec=_make_spec(),
            architect=SimpleArchitect(),
            backend=EchoBackend(),
            max_steps=0,
        )
        assert state.current_step == 0
        assert state.history == []
        assert state.done is False

    def test_architect_returns_none_immediately(self) -> None:
        """Architect that never wants to do anything."""

        class NullArchitect:
            def next_instruction(self, state: OrchestratorState) -> Instruction | None:
                return None

            def review_result(self, state: OrchestratorState, result: StepResult) -> bool:
                return True

        state = run_loop(
            spec=_make_spec(),
            architect=NullArchitect(),
            backend=EchoBackend(),
            max_steps=5,
        )
        assert state.current_step == 0
        assert state.done is True
        assert state.history == []
