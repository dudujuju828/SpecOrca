"""Tests for stub implementations (SimpleArchitect, EchoBackend)."""

from __future__ import annotations

from pathlib import Path

from spec_orchestrator.models import (
    OrchestratorState,
    Spec,
    SpecFormat,
    StepResult,
    StepStatus,
)
from spec_orchestrator.stubs import EchoBackend, SimpleArchitect


def _make_spec() -> Spec:
    return Spec(
        source=Path("/tmp/test.md"),
        format=SpecFormat.MARKDOWN,
        title="Test Spec",
        raw_content="# Test Spec\nContent.",
    )


def _make_state(**overrides: object) -> OrchestratorState:
    defaults: dict[str, object] = {
        "spec": _make_spec(),
        "max_steps": 3,
    }
    defaults.update(overrides)
    return OrchestratorState(**defaults)  # type: ignore[arg-type]


class TestSimpleArchitect:
    def test_returns_instruction(self) -> None:
        architect = SimpleArchitect()
        state = _make_state()

        instr = architect.next_instruction(state)

        assert instr is not None
        assert instr.step_index == 0
        assert "Test Spec" in instr.prompt

    def test_returns_none_when_done(self) -> None:
        architect = SimpleArchitect()
        state = _make_state(done=True)

        assert architect.next_instruction(state) is None

    def test_returns_none_at_max_steps(self) -> None:
        architect = SimpleArchitect()
        state = _make_state(current_step=3, max_steps=3)

        assert architect.next_instruction(state) is None

    def test_review_continues_on_success(self) -> None:
        architect = SimpleArchitect()
        state = _make_state(current_step=1)
        result = StepResult(step_index=0, status=StepStatus.SUCCESS, output="ok")

        assert architect.review_result(state, result) is True

    def test_review_stops_on_failure(self) -> None:
        architect = SimpleArchitect()
        state = _make_state(current_step=1)
        result = StepResult(step_index=0, status=StepStatus.FAILURE, output="fail")

        assert architect.review_result(state, result) is False

    def test_review_stops_at_max_steps(self) -> None:
        architect = SimpleArchitect()
        state = _make_state(current_step=3, max_steps=3)
        result = StepResult(step_index=2, status=StepStatus.SUCCESS, output="ok")

        assert architect.review_result(state, result) is False


class TestEchoBackend:
    def test_returns_success(self) -> None:
        backend = EchoBackend()
        spec = _make_spec()
        from spec_orchestrator.models import Instruction

        instr = Instruction(spec=spec, step_index=0, prompt="do something")

        result = backend.execute(instr)

        assert result.status == StepStatus.SUCCESS
        assert result.step_index == 0

    def test_echoes_prompt(self) -> None:
        backend = EchoBackend()
        spec = _make_spec()
        from spec_orchestrator.models import Instruction

        instr = Instruction(spec=spec, step_index=1, prompt="build widgets")

        result = backend.execute(instr)

        assert "[echo] build widgets" in result.output
