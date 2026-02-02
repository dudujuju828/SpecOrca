"""Tests for core data models."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from spec_orchestrator.models import (
    Instruction,
    OrchestratorState,
    Spec,
    SpecFormat,
    StepResult,
    StepStatus,
)


def _make_spec(**overrides: object) -> Spec:
    defaults: dict[str, object] = {
        "source": Path("/tmp/test.md"),
        "format": SpecFormat.MARKDOWN,
        "title": "Test Spec",
        "raw_content": "# Test Spec\nDo something.",
    }
    defaults.update(overrides)
    return Spec(**defaults)  # type: ignore[arg-type]


class TestSpecFormat:
    def test_values(self) -> None:
        assert SpecFormat.MARKDOWN.value == "markdown"
        assert SpecFormat.YAML.value == "yaml"


class TestStepStatus:
    def test_values(self) -> None:
        assert StepStatus.SUCCESS.value == "success"
        assert StepStatus.FAILURE.value == "failure"
        assert StepStatus.ERROR.value == "error"


class TestSpec:
    def test_fields_accessible(self) -> None:
        spec = _make_spec()
        assert spec.title == "Test Spec"
        assert spec.format == SpecFormat.MARKDOWN

    def test_frozen(self) -> None:
        spec = _make_spec()
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.title = "changed"  # type: ignore[misc]


class TestInstruction:
    def test_fields_accessible(self) -> None:
        spec = _make_spec()
        instr = Instruction(spec=spec, step_index=0, prompt="do it")
        assert instr.step_index == 0
        assert instr.prompt == "do it"
        assert instr.spec is spec

    def test_frozen(self) -> None:
        instr = Instruction(spec=_make_spec(), step_index=0, prompt="x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            instr.prompt = "y"  # type: ignore[misc]


class TestStepResult:
    def test_fields_accessible(self) -> None:
        result = StepResult(step_index=1, status=StepStatus.SUCCESS, output="ok")
        assert result.step_index == 1
        assert result.status == StepStatus.SUCCESS
        assert result.output == "ok"

    def test_frozen(self) -> None:
        result = StepResult(step_index=0, status=StepStatus.SUCCESS, output="ok")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.output = "changed"  # type: ignore[misc]


class TestOrchestratorState:
    def test_defaults(self) -> None:
        state = OrchestratorState(spec=_make_spec(), max_steps=5)
        assert state.current_step == 0
        assert state.history == []
        assert state.done is False

    def test_mutable(self) -> None:
        state = OrchestratorState(spec=_make_spec(), max_steps=5)
        state.current_step = 3
        state.done = True
        assert state.current_step == 3
        assert state.done is True
