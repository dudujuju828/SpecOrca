"""End-to-end CLI tests using subprocess (no in-process imports).

These tests invoke ``spec-orchestrator`` as a child process to verify the
full installed entry-point behaviour, including argument parsing, spec loading,
backend execution, and output formatting.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run spec-orchestrator as a subprocess via ``python -m spec_orchestrator.cli``."""
    return subprocess.run(
        [sys.executable, "-m", "spec_orchestrator.cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestE2EHelp:
    def test_help(self) -> None:
        proc = _run_cli("--help")
        assert proc.returncode == 0
        assert "spec-orchestrator" in proc.stdout

    def test_version(self) -> None:
        proc = _run_cli("--version")
        assert proc.returncode == 0
        assert "0.1.0" in proc.stdout

    def test_run_help(self) -> None:
        proc = _run_cli("run", "--help")
        assert proc.returncode == 0
        assert "--spec" in proc.stdout
        assert "--max-steps" in proc.stdout
        assert "--backend" in proc.stdout
        assert "--auto-commit" in proc.stdout


class TestE2ERunMockBackend:
    def test_single_step_mock(self, tmp_path: Path) -> None:
        spec = tmp_path / "feature.md"
        spec.write_text("# Add widgets\nImplement widget support.\n", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec), "--backend", "mock")

        assert proc.returncode == 0
        assert "[step 0]" in proc.stdout
        assert "[mock]" in proc.stdout
        assert "Completed after 1 step(s)." in proc.stdout

    def test_multi_step_mock(self, tmp_path: Path) -> None:
        spec = tmp_path / "feature.md"
        spec.write_text("# Multi step\nDo three things.\n", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec), "--backend", "mock", "--max-steps", "3")

        assert proc.returncode == 0
        assert "[step 0]" in proc.stdout
        assert "[step 1]" in proc.stdout
        assert "[step 2]" in proc.stdout

    def test_yaml_spec(self, tmp_path: Path) -> None:
        spec = tmp_path / "feature.yaml"
        spec.write_text("title: YAML Feature\nsteps:\n  - one\n", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec), "--backend", "mock")

        assert proc.returncode == 0
        assert "[step 0]" in proc.stdout

    def test_default_backend_is_mock(self, tmp_path: Path) -> None:
        """Without --backend, the default should be mock (not claude)."""
        spec = tmp_path / "feature.md"
        spec.write_text("# Test\nGo.\n", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec))

        # Should succeed — if default was claude it would fail (not installed).
        assert proc.returncode == 0


class TestE2EErrors:
    def test_missing_spec_file(self) -> None:
        proc = _run_cli("run", "--spec", "/nonexistent/path/spec.md")

        assert proc.returncode == 1
        assert "Error:" in proc.stderr

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.txt"
        spec.write_text("hello", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec))

        assert proc.returncode == 1
        assert "Unsupported" in proc.stderr

    def test_missing_required_spec_flag(self) -> None:
        proc = _run_cli("run")

        assert proc.returncode == 2  # argparse exits 2 on missing required args
        assert "required" in proc.stderr.lower() or "spec" in proc.stderr.lower()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Invalid backend choice caught by argparse on all platforms",
    )
    def test_invalid_backend_choice(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text("# Test\nGo.\n", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec), "--backend", "nonexistent")

        # argparse rejects invalid choices with exit code 2
        assert proc.returncode == 2
