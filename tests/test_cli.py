"""Tests for the spec-orchestrator CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_orchestrator import __version__
from spec_orchestrator.cli import build_parser, main


class TestBuildParser:
    def test_returns_parser(self) -> None:
        parser = build_parser()
        assert parser.prog == "spec-orchestrator"

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit, match="0"):
            build_parser().parse_args(["--version"])
        assert __version__ in capsys.readouterr().out


class TestMain:
    def test_help_printed_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main([])
        assert rc == 0
        assert "spec-orchestrator" in capsys.readouterr().out

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
