"""End-to-end CLI tests using subprocess (no in-process imports).

These tests invoke ``spec-orca`` as a child process to verify the
full installed entry-point behaviour, including argument parsing, spec loading,
backend execution, and output formatting.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(
    *args: str, timeout: int = 30, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run spec-orca as a subprocess via ``python -m spec_orca.cli``."""
    return subprocess.run(
        [sys.executable, "-m", "spec_orca.cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd is not None else None,
    )


def _git_available() -> bool:
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


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "init")
    return repo


class TestE2EHelp:
    def test_help(self) -> None:
        proc = _run_cli("--help")
        assert proc.returncode == 0
        assert "spec-orca" in proc.stdout

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
        assert "--goal" in proc.stdout
        assert "--state" in proc.stdout
        assert "--stop-on-failure" in proc.stdout
        assert "--continue-on-failure" in proc.stdout


class TestE2ERunMockBackend:
    def test_single_step_mock(self, tmp_path: Path) -> None:
        spec = tmp_path / "feature.yaml"
        spec.write_text(
            """goal: "Run"
specs:
  - id: "one"
    title: "One"
    acceptance_criteria: ["done"]
""",
            encoding="utf-8",
        )

        proc = _run_cli("run", "--spec", str(spec), "--backend", "mock")

        assert proc.returncode == 0
        assert "Progress:" in proc.stdout
        assert "one" in proc.stdout

    def test_multi_step_mock(self, tmp_path: Path) -> None:
        spec = tmp_path / "feature.yaml"
        spec.write_text(
            """goal: "Run"
specs:
  - id: "one"
    title: "One"
    acceptance_criteria: ["done"]
  - id: "two"
    title: "Two"
    acceptance_criteria: ["done"]
""",
            encoding="utf-8",
        )

        proc = _run_cli("run", "--spec", str(spec), "--backend", "mock", "--max-steps", "2")

        assert proc.returncode == 0
        assert "0" in proc.stdout
        assert "1" in proc.stdout

    def test_default_backend_is_mock(self, tmp_path: Path) -> None:
        """Without --backend, the default should be mock (not claude)."""
        spec = tmp_path / "feature.yaml"
        spec.write_text(
            """goal: "Default"
specs:
  - id: "one"
    title: "One"
    acceptance_criteria: ["done"]
""",
            encoding="utf-8",
        )

        proc = _run_cli("run", "--spec", str(spec))

        # Should succeed — if default was claude it would fail (not installed).
        assert proc.returncode == 0


@pytest.mark.skipif(not _git_available(), reason="git not available")
class TestE2EStatePersistence:
    def test_run_writes_state_in_git_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        spec = repo / "spec.yaml"
        spec.write_text(
            """goal: "Persist"
specs:
  - id: "one"
    title: "One"
    acceptance_criteria: ["done"]
""",
            encoding="utf-8",
        )
        state_path = repo / "state.json"

        proc = _run_cli(
            "run",
            "--spec",
            str(spec),
            "--backend",
            "mock",
            "--max-steps",
            "1",
            "--state",
            str(state_path),
            cwd=repo,
        )

        assert proc.returncode == 0
        assert "Progress:" in proc.stdout
        assert state_path.exists()

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert payload["repo_path"] == str(repo.resolve())
        assert payload["history"]


class TestE2EErrors:
    def test_missing_spec_file(self) -> None:
        proc = _run_cli("run", "--spec", "/nonexistent/path/spec.yaml")

        assert proc.returncode == 1
        assert "Error:" in proc.stderr

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.txt"
        spec.write_text("hello", encoding="utf-8")

        proc = _run_cli("run", "--spec", str(spec))

        assert proc.returncode == 1
        assert "Unsupported" in proc.stderr or "Error:" in proc.stderr

    def test_missing_required_spec_flag(self) -> None:
        proc = _run_cli("run")

        assert proc.returncode == 2  # argparse exits 2 on missing required args
        assert "required" in proc.stderr.lower() or "spec" in proc.stderr.lower()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Invalid backend choice caught by argparse on all platforms",
    )
    def test_invalid_backend_choice(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.yaml"
        spec.write_text(
            """goal: "Bad"
specs:
  - id: "one"
    title: "One"
    acceptance_criteria: ["done"]
""",
            encoding="utf-8",
        )

        proc = _run_cli("run", "--spec", str(spec), "--backend", "nonexistent")

        # argparse rejects invalid choices with exit code 2
        assert proc.returncode == 2
