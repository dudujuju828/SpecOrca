"""Tests for core data models."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest

from spec_orca.models import (
    Context,
    Instruction,
    OrchestratorState,
    Result,
    ResultStatus,
    Spec,
    SpecFormat,
    SpecStatus,
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


# -- Enumerations ----------------------------------------------------------


class TestSpecFormat:
    def test_values(self) -> None:
        assert SpecFormat.MARKDOWN.value == "markdown"
        assert SpecFormat.YAML.value == "yaml"


class TestSpecStatus:
    def test_values(self) -> None:
        assert SpecStatus.PENDING.value == "pending"
        assert SpecStatus.IN_PROGRESS.value == "in_progress"
        assert SpecStatus.DONE.value == "done"
        assert SpecStatus.FAILED.value == "failed"
        assert SpecStatus.SKIPPED.value == "skipped"

    def test_member_count(self) -> None:
        assert len(SpecStatus) == 5


class TestStepStatus:
    def test_values(self) -> None:
        assert StepStatus.SUCCESS.value == "success"
        assert StepStatus.FAILURE.value == "failure"
        assert StepStatus.ERROR.value == "error"


class TestResultStatus:
    def test_values(self) -> None:
        assert ResultStatus.SUCCESS.value == "success"
        assert ResultStatus.PARTIAL.value == "partial"
        assert ResultStatus.FAILURE.value == "failure"
        assert ResultStatus.ERROR.value == "error"

    def test_member_count(self) -> None:
        assert len(ResultStatus) == 4


# -- Spec -------------------------------------------------------------------


class TestSpec:
    def test_fields_accessible(self) -> None:
        spec = _make_spec()
        assert spec.title == "Test Spec"
        assert spec.format == SpecFormat.MARKDOWN

    def test_frozen(self) -> None:
        spec = _make_spec()
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.title = "changed"  # type: ignore[misc]

    def test_auto_generated_id(self) -> None:
        spec = _make_spec()
        assert isinstance(spec.id, str)
        assert len(spec.id) == 12

    def test_unique_ids(self) -> None:
        a = _make_spec()
        b = _make_spec()
        assert a.id != b.id

    def test_default_status(self) -> None:
        spec = _make_spec()
        assert spec.status == SpecStatus.PENDING

    def test_default_description(self) -> None:
        spec = _make_spec()
        assert spec.description == ""

    def test_default_acceptance_criteria(self) -> None:
        spec = _make_spec()
        assert spec.acceptance_criteria == []

    def test_default_dependencies(self) -> None:
        spec = _make_spec()
        assert spec.dependencies == []

    def test_default_attempts(self) -> None:
        spec = _make_spec()
        assert spec.attempts == 0

    def test_created_at_is_utc(self) -> None:
        spec = _make_spec()
        assert isinstance(spec.created_at, datetime)
        assert spec.created_at.tzinfo == UTC

    def test_custom_fields(self) -> None:
        spec = _make_spec(
            description="A test",
            acceptance_criteria=["crit1", "crit2"],
            dependencies=["dep-abc"],
            status=SpecStatus.IN_PROGRESS,
            attempts=3,
        )
        assert spec.description == "A test"
        assert spec.acceptance_criteria == ["crit1", "crit2"]
        assert spec.dependencies == ["dep-abc"]
        assert spec.status == SpecStatus.IN_PROGRESS
        assert spec.attempts == 3

    def test_list_defaults_are_not_shared(self) -> None:
        a = _make_spec()
        b = _make_spec()
        assert a.acceptance_criteria is not b.acceptance_criteria
        assert a.dependencies is not b.dependencies


# -- Instruction ------------------------------------------------------------


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


# -- StepResult -------------------------------------------------------------


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

    def test_default_files_touched(self) -> None:
        result = StepResult(step_index=0, status=StepStatus.SUCCESS, output="ok")
        assert result.files_touched == ()

    def test_default_commands_run(self) -> None:
        result = StepResult(step_index=0, status=StepStatus.SUCCESS, output="ok")
        assert result.commands_run == ()


# -- Result -----------------------------------------------------------------


class TestResult:
    def test_required_fields(self) -> None:
        result = Result(status=ResultStatus.SUCCESS, summary="All good")
        assert result.status == ResultStatus.SUCCESS
        assert result.summary == "All good"

    def test_defaults(self) -> None:
        result = Result(status=ResultStatus.SUCCESS, summary="ok")
        assert result.details == ""
        assert result.files_changed == []
        assert result.commands_run == []
        assert result.error is None
        assert result.structured_output is None

    def test_frozen(self) -> None:
        result = Result(status=ResultStatus.SUCCESS, summary="ok")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.summary = "changed"  # type: ignore[misc]

    def test_error_result(self) -> None:
        result = Result(
            status=ResultStatus.ERROR,
            summary="Failed",
            error="something broke",
        )
        assert result.error == "something broke"

    def test_custom_fields(self) -> None:
        result = Result(
            status=ResultStatus.PARTIAL,
            summary="Partially done",
            details="Step 2 failed",
            files_changed=["a.py", "b.py"],
            commands_run=["ruff check ."],
            structured_output={"status": "partial", "summary": "Partially done"},
        )
        assert result.files_changed == ["a.py", "b.py"]
        assert result.commands_run == ["ruff check ."]
        assert result.structured_output == {"status": "partial", "summary": "Partially done"}

    def test_list_defaults_are_not_shared(self) -> None:
        a = Result(status=ResultStatus.SUCCESS, summary="ok")
        b = Result(status=ResultStatus.SUCCESS, summary="ok")
        assert a.files_changed is not b.files_changed
        assert a.commands_run is not b.commands_run


# -- Context ----------------------------------------------------------------


class TestContext:
    def test_required_fields(self) -> None:
        ctx = Context(
            repo_path=Path("/repo"),
            spec_path=Path("/repo/spec.md"),
            goal="build widgets",
            backend_name="mock",
        )
        assert ctx.repo_path == Path("/repo")
        assert ctx.goal == "build widgets"
        assert ctx.backend_name == "mock"

    def test_defaults(self) -> None:
        ctx = Context(
            repo_path=Path("/repo"),
            spec_path=Path("/repo/spec.md"),
            goal="test",
            backend_name="mock",
        )
        assert ctx.step == 0
        assert ctx.max_steps == 1

    def test_auto_generated_run_id(self) -> None:
        ctx = Context(
            repo_path=Path("/repo"),
            spec_path=Path("/repo/spec.md"),
            goal="test",
            backend_name="mock",
        )
        assert isinstance(ctx.run_id, str)
        assert len(ctx.run_id) == 12

    def test_unique_run_ids(self) -> None:
        a = Context(repo_path=Path("/r"), spec_path=Path("/s"), goal="g", backend_name="mock")
        b = Context(repo_path=Path("/r"), spec_path=Path("/s"), goal="g", backend_name="mock")
        assert a.run_id != b.run_id

    def test_frozen(self) -> None:
        ctx = Context(
            repo_path=Path("/repo"),
            spec_path=Path("/repo/spec.md"),
            goal="test",
            backend_name="mock",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.step = 5  # type: ignore[misc]


# -- OrchestratorState ------------------------------------------------------


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
