"""Tests for the SpecOrca CLI."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from spec_orca import __version__
from spec_orca.cli import build_parser, main


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


def _git_available() -> bool:
    import subprocess

    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


class TestBuildParser:
    def test_returns_parser(self) -> None:
        parser = build_parser()
        assert parser.prog == "spec-orca"

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit, match="0"):
            build_parser().parse_args(["--version"])
        assert __version__ in capsys.readouterr().out

    def test_run_subparser_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--spec", "foo.yaml"])
        assert args.command == "run"
        assert args.spec == Path("foo.yaml")

    def test_plan_subparser_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["plan", "--spec", "foo.yaml"])
        assert args.command == "plan"
        assert args.spec == Path("foo.yaml")

    def test_doctor_subparser_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"

    def test_stop_on_failure_default_true(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--spec", "foo.yaml"])
        assert args.stop_on_failure is True


class TestMain:
    def test_help_printed_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main([])
        assert rc == 0
        assert "spec-orca" in capsys.readouterr().out

    def test_returns_zero(self) -> None:
        assert main([]) == 0


class TestRunSubcommand:
    def test_run_with_yaml_spec(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        rc = main(["run", "--spec", str(yml), "--backend", "mock"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Progress:" in out
        assert "a" in out

    def test_run_missing_spec(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["run", "--spec", "/nonexistent/spec.yaml"])

        assert rc == 1
        assert "Error:" in capsys.readouterr().err

    def test_run_no_spec_flag(self) -> None:
        with pytest.raises(SystemExit, match="2"):
            main(["run"])


class TestPlanSubcommand:
    def test_plan_prints_ordered_specs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        yml = tmp_path / "spec.yaml"
        yml.write_text(
            """goal: "Plan"
specs:
  - id: "first"
    title: "First"
    acceptance_criteria: ["ok"]
  - id: "second"
    title: "Second"
    acceptance_criteria: ["ok"]
    dependencies: ["first"]
""",
            encoding="utf-8",
        )

        rc = main(["plan", "--spec", str(yml)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "1. first" in out
        assert "2. second" in out


class TestDoctorSubcommand:
    @pytest.mark.skipif(not _git_available(), reason="git not available")
    def test_doctor_with_spec(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        rc = main(["doctor", "--spec", str(yml), "--backend", "mock"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "python: OK" in out
        assert "git:" in out

    def test_doctor_missing_spec_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["doctor", "--spec", "/nope/spec.yaml", "--backend", "mock"])

        assert rc == 1
        out = capsys.readouterr().out
        assert "spec: FAIL" in out


class TestRunAutoCommit:
    """CLI auto-commit integration (mocked git layer)."""

    def test_auto_commit_skipped_no_changes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        with mock.patch("spec_orca.dev.git.auto_commit", return_value=False):
            rc = main(["run", "--spec", str(yml), "--auto-commit"])

        assert rc == 0
        assert "Auto-commit skipped" in capsys.readouterr().out

    def test_auto_commit_created(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        with mock.patch("spec_orca.dev.git.auto_commit", return_value=True):
            rc = main(["run", "--spec", str(yml), "--auto-commit"])

        assert rc == 0
        assert "Auto-commit created" in capsys.readouterr().out

    def test_auto_commit_with_prefix(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        with mock.patch("spec_orca.dev.git.auto_commit", return_value=True) as mocked:
            rc = main(
                [
                    "run",
                    "--spec",
                    str(yml),
                    "--auto-commit",
                    "--commit-prefix",
                    "feat",
                ]
            )

        assert rc == 0
        mocked.assert_called_once()
        call_kwargs = mocked.call_args
        assert call_kwargs.kwargs["prefix"] == "feat"

    def test_auto_commit_git_error_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from spec_orca.dev.git import GitError

        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        with mock.patch(
            "spec_orca.dev.git.auto_commit",
            side_effect=GitError("not a git repo"),
        ):
            rc = main(["run", "--spec", str(yml), "--auto-commit"])

        assert rc == 1
        assert "Auto-commit failed" in capsys.readouterr().err

    def test_auto_commit_off_by_default(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without --auto-commit, the git module is never imported/called."""
        yml = tmp_path / "spec.yaml"
        _write_spec(yml)

        with mock.patch("spec_orca.dev.git.auto_commit") as mocked:
            rc = main(["run", "--spec", str(yml)])

        assert rc == 0
        mocked.assert_not_called()
