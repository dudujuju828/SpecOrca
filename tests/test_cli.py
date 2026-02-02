"""Tests for the spec-orchestrator CLI."""

from __future__ import annotations

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
