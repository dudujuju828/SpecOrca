"""Tests for the run-report system (render_report + --report CLI flag)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from spec_orca.cli import main
from spec_orca.models import Context, Result, ResultStatus, Spec
from spec_orca.orchestrator import ExecutionSummary, RunStep
from spec_orca.report import render_report

# -- helpers ----------------------------------------------------------------


def _make_context(goal: str = "Test goal") -> Context:
    return Context(
        repo_path=Path("/tmp"),
        spec_path=Path("/tmp/spec.yaml"),
        goal=goal,
        backend_name="mock",
        run_id="abc123",
        max_steps=3,
    )


def _make_summary(
    *,
    results: list[Result] | None = None,
    step_details: list[RunStep] | None = None,
    specs: list[Spec] | None = None,
    completed: int = 1,
    failed: int = 0,
    pending: int = 0,
    in_progress: int = 0,
    stopped_reason: str = "no_runnable_specs",
) -> ExecutionSummary:
    results = results or []
    step_details = step_details or []
    specs = specs or []
    return ExecutionSummary(
        steps=len(step_details),
        results=results,
        step_details=step_details,
        specs=specs,
        completed=completed,
        failed=failed,
        pending=pending,
        in_progress=in_progress,
        stopped_reason=stopped_reason,
    )


def _success_result(summary: str = "All good") -> Result:
    return Result(
        status=ResultStatus.SUCCESS,
        summary=summary,
        files_changed=["src/main.py"],
    )


def _failure_result(summary: str = "Something broke", error: str = "crash") -> Result:
    return Result(
        status=ResultStatus.FAILURE,
        summary=summary,
        error=error,
    )


def _make_step(
    index: int,
    spec_id: str,
    title: str,
    result: Result,
    attempts: int = 1,
) -> RunStep:
    return RunStep(
        index=index,
        spec_id=spec_id,
        title=title,
        result=result,
        attempts=attempts,
    )


def _write_spec(path: Path) -> None:
    path.write_text(
        """goal: "Test goal"
specs:
  - id: "a"
    title: "A"
    acceptance_criteria: ["done"]
""",
        encoding="utf-8",
    )


# -- render_report unit tests ----------------------------------------------


class TestRenderReportHeading:
    """render_report returns valid Markdown with the goal as a heading."""

    def test_goal_is_top_level_heading(self) -> None:
        context = _make_context(goal="Build the widget")
        summary = _make_summary()

        md = render_report(summary, context)

        assert md.startswith("# Build the widget\n")

    def test_contains_metadata_section(self) -> None:
        context = _make_context()
        summary = _make_summary()

        md = render_report(summary, context)

        assert "## Metadata" in md
        assert "**Backend:** mock" in md
        assert "**Run ID:** abc123" in md

    def test_contains_results_and_details_sections(self) -> None:
        context = _make_context()
        summary = _make_summary()

        md = render_report(summary, context)

        assert "## Results" in md
        assert "## Spec Details" in md
        assert "## Totals" in md


class TestRenderReportResultsTable:
    """The results table contains spec IDs and statuses."""

    def test_table_contains_spec_ids_and_statuses(self) -> None:
        step = _make_step(0, "spec-1", "First spec", _success_result())
        summary = _make_summary(
            results=[_success_result()],
            step_details=[step],
        )

        md = render_report(summary, _make_context())

        assert "| spec-1 |" in md
        assert "| pass |" in md

    def test_table_with_multiple_specs(self) -> None:
        steps = [
            _make_step(0, "spec-1", "First", _success_result()),
            _make_step(1, "spec-2", "Second", _failure_result()),
        ]
        summary = _make_summary(
            results=[_success_result(), _failure_result()],
            step_details=steps,
            completed=1,
            failed=1,
        )

        md = render_report(summary, _make_context())

        assert "spec-1" in md
        assert "spec-2" in md
        assert "pass" in md
        assert "FAIL" in md

    def test_table_has_header_row(self) -> None:
        step = _make_step(0, "s1", "T", _success_result())
        summary = _make_summary(step_details=[step], results=[_success_result()])

        md = render_report(summary, _make_context())

        assert "| Step | Spec ID | Title | Status | Attempts |" in md


class TestRenderReportErrorDetails:
    """Error details appear in the report when a spec fails."""

    def test_error_appears_in_spec_details(self) -> None:
        fail = _failure_result(summary="Broken", error="segfault in module X")
        step = _make_step(0, "spec-err", "Error spec", fail)
        summary = _make_summary(
            results=[fail],
            step_details=[step],
            completed=0,
            failed=1,
            stopped_reason="failure",
        )

        md = render_report(summary, _make_context())

        assert "**Error:** segfault in module X" in md

    def test_no_error_section_when_no_error(self) -> None:
        ok = _success_result()
        step = _make_step(0, "s1", "OK spec", ok)
        summary = _make_summary(results=[ok], step_details=[step])

        md = render_report(summary, _make_context())

        assert "**Error:**" not in md

    def test_files_changed_listed(self) -> None:
        ok = _success_result()
        step = _make_step(0, "s1", "OK spec", ok)
        summary = _make_summary(results=[ok], step_details=[step])

        md = render_report(summary, _make_context())

        assert "`src/main.py`" in md


# -- CLI --report flag integration test ------------------------------------


class TestReportCLIFlag:
    """The --report CLI flag writes a Markdown report file."""

    def test_report_flag_writes_file(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        spec_file = tmp_path / "spec.yaml"
        _write_spec(spec_file)
        report_file = tmp_path / "report.md"

        rc = main(
            [
                "run",
                "--spec",
                str(spec_file),
                "--backend",
                "mock",
                "--report",
                str(report_file),
            ]
        )

        assert rc == 0
        assert report_file.exists()

        content = report_file.read_text(encoding="utf-8")
        # Goal from the spec file should be the heading
        assert content.startswith("# Test goal\n")
        # Should contain the spec ID from the spec file
        assert "a" in content
        # Should contain results section
        assert "## Results" in content

        out = capsys.readouterr().out
        assert "Report written to" in out

    def test_report_not_written_without_flag(
        self,
        tmp_path: Path,
    ) -> None:
        spec_file = tmp_path / "spec.yaml"
        _write_spec(spec_file)
        report_file = tmp_path / "report.md"

        rc = main(
            [
                "run",
                "--spec",
                str(spec_file),
                "--backend",
                "mock",
            ]
        )

        assert rc == 0
        assert not report_file.exists()

    def test_report_written_on_failure(
        self,
        tmp_path: Path,
    ) -> None:
        """Report is still written even when the run has failures."""
        from spec_orca.backends.mock import MockBackend, MockBackendConfig

        spec_file = tmp_path / "spec.yaml"
        _write_spec(spec_file)
        report_file = tmp_path / "report.md"

        failing_backend = MockBackend(
            config=MockBackendConfig(
                status=ResultStatus.FAILURE,
                summary="fail",
                error="something went wrong",
            )
        )

        with mock.patch("spec_orca.backends.create_backend", return_value=failing_backend):
            rc = main(
                [
                    "run",
                    "--spec",
                    str(spec_file),
                    "--backend",
                    "mock",
                    "--report",
                    str(report_file),
                ]
            )

        assert rc == 1
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "FAIL" in content
        assert "something went wrong" in content
