"""Tests for the SpecOrca CLI."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from spec_orca import __version__
from spec_orca.cli import build_parser, main


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
        # Should parse without error
        args = parser.parse_args(["run", "--spec", "foo.md"])
        assert args.command == "run"
        assert args.spec == Path("foo.md")

    def test_auto_commit_defaults_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--spec", "foo.md"])
        assert args.auto_commit is False

    def test_commit_prefix_defaults_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--spec", "foo.md"])
        assert args.commit_prefix is None

    def test_backend_defaults_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--spec", "foo.md"])
        assert args.backend is None


class TestMain:
    def test_help_printed_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main([])
        assert rc == 0
        assert "spec-orca" in capsys.readouterr().out

    def test_returns_zero(self) -> None:
        assert main([]) == 0


class TestRunSubcommand:
    def test_run_with_markdown_spec(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md = tmp_path / "spec.md"
        md.write_text("# My Feature\nBuild it.\n", encoding="utf-8")

        rc = main(["run", "--spec", str(md)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "[step 0]" in out
        assert "Completed after 1 step(s)." in out

    def test_run_with_yaml_spec(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        yml = tmp_path / "spec.yaml"
        yml.write_text("title: YAML Feature\nsteps:\n  - one\n", encoding="utf-8")

        rc = main(["run", "--spec", str(yml)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "[step 0]" in out
        assert "YAML Feature" in out or "Completed" in out

    def test_run_missing_spec(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["run", "--spec", "/nonexistent/spec.md"])

        assert rc == 1
        assert "Error:" in capsys.readouterr().err

    def test_run_max_steps(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "spec.md"
        md.write_text("# Multi\nSteps.\n", encoding="utf-8")

        rc = main(["run", "--spec", str(md), "--max-steps", "3"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "[step 0]" in out
        assert "[step 1]" in out
        assert "[step 2]" in out

    def test_run_no_spec_flag(self) -> None:
        with pytest.raises(SystemExit, match="2"):
            main(["run"])

    def test_run_with_backend_mock(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md = tmp_path / "spec.md"
        md.write_text("# Backend Test\nDo it.\n", encoding="utf-8")

        rc = main(["run", "--spec", str(md), "--backend", "mock"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "[mock]" in out

    def test_run_backend_env_var(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SPEC_ORCA_BACKEND", "mock")
        md = tmp_path / "spec.md"
        md.write_text("# Env Test\nDo it.\n", encoding="utf-8")

        rc = main(["run", "--spec", str(md)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "[mock]" in out

    def test_run_unsupported_spec_extension(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        txt = tmp_path / "spec.txt"
        txt.write_text("hello", encoding="utf-8")

        rc = main(["run", "--spec", str(txt)])

        assert rc == 1
        assert "Unsupported" in capsys.readouterr().err


class TestRunAutoCommit:
    """CLI auto-commit integration (mocked git layer)."""

    def test_auto_commit_skipped_no_changes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md = tmp_path / "spec.md"
        md.write_text("# Test\nDo it.\n", encoding="utf-8")

        with mock.patch("spec_orca.dev.git.auto_commit", return_value=False):
            rc = main(["run", "--spec", str(md), "--auto-commit"])

        assert rc == 0
        assert "Auto-commit skipped (no changes)." in capsys.readouterr().out

    def test_auto_commit_created(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "spec.md"
        md.write_text("# Test\nDo it.\n", encoding="utf-8")

        with mock.patch("spec_orca.dev.git.auto_commit", return_value=True):
            rc = main(["run", "--spec", str(md), "--auto-commit"])

        assert rc == 0
        assert "Auto-commit created." in capsys.readouterr().out

    def test_auto_commit_with_prefix(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md = tmp_path / "spec.md"
        md.write_text("# Feat\nDo it.\n", encoding="utf-8")

        with mock.patch("spec_orca.dev.git.auto_commit", return_value=True) as mocked:
            rc = main(
                [
                    "run",
                    "--spec",
                    str(md),
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

        md = tmp_path / "spec.md"
        md.write_text("# Test\nDo it.\n", encoding="utf-8")

        with mock.patch(
            "spec_orca.dev.git.auto_commit",
            side_effect=GitError("not a git repo"),
        ):
            rc = main(["run", "--spec", str(md), "--auto-commit"])

        assert rc == 1
        assert "Auto-commit failed" in capsys.readouterr().err

    def test_auto_commit_off_by_default(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without --auto-commit, the git module is never imported/called."""
        md = tmp_path / "spec.md"
        md.write_text("# Test\nDo it.\n", encoding="utf-8")

        with mock.patch("spec_orca.dev.git.auto_commit") as mocked:
            rc = main(["run", "--spec", str(md)])

        assert rc == 0
        mocked.assert_not_called()
