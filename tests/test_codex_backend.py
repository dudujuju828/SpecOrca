"""Tests for the Codex backend."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from spec_orca.backends import CodexBackend, CodexConfig
from spec_orca.git_ops import GitStatusDelta
from spec_orca.models import Context, ResultStatus, Spec, SpecFormat


def _make_spec() -> Spec:
    return Spec(
        source=Path("/tmp/test.md"),
        format=SpecFormat.MARKDOWN,
        title="Test Spec",
        raw_content="# Test Spec\nContent.",
    )


def _make_context() -> Context:
    return Context(
        repo_path=Path("/tmp"),
        spec_path=Path("/tmp/spec.md"),
        goal="test goal",
        backend_name="codex",
    )


@pytest.fixture(autouse=True)
def _stub_git_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "spec_orca.backends.codex.compute_status_delta",
        lambda *_args, **_kwargs: (GitStatusDelta(changed=[]), None),
    )


def test_missing_executable_returns_failure() -> None:
    backend = CodexBackend(CodexConfig(executable="nonexistent-codex-xyz"))

    result = backend.execute(_make_spec(), _make_context())

    assert result.status == ResultStatus.FAILURE
    assert "not found" in (result.error or "").lower()


def test_success_with_json_response() -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))
    fake_proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(
            {
                "result": json.dumps(
                    {
                        "status": "success",
                        "summary": "Completed.",
                        "details": "done",
                        "commands_run": ["pytest"],
                        "error": None,
                    }
                )
            }
        ),
        stderr="",
    )

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=fake_proc),
    ):
        result = backend.execute(_make_spec(), _make_context())

    assert result.status == ResultStatus.SUCCESS
    assert result.summary == "Completed."
    assert result.commands_run == ["pytest"]


def test_success_with_plain_text_response() -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))
    fake_proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="plain text response",
        stderr="",
    )

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=fake_proc),
    ):
        result = backend.execute(_make_spec(), _make_context())

    assert result.status == ResultStatus.SUCCESS
    assert result.summary == "plain text response"


def test_nonzero_exit_returns_failure() -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))
    fake_proc = subprocess.CompletedProcess(
        args=[],
        returncode=2,
        stdout="",
        stderr="failed hard",
    )

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=fake_proc),
    ):
        result = backend.execute(_make_spec(), _make_context())

    assert result.status == ResultStatus.FAILURE
    assert "failed hard" in (result.error or "")


def test_timeout_returns_failure() -> None:
    backend = CodexBackend(CodexConfig(executable="codex", timeout=7))

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("codex", 7),
        ),
    ):
        result = backend.execute(_make_spec(), _make_context())

    assert result.status == ResultStatus.FAILURE
    assert "timed out" in (result.error or "").lower()


def test_command_includes_required_flags() -> None:
    backend = CodexBackend(
        CodexConfig(
            executable="codex",
            timeout=10,
            model="gpt-5-codex",
        )
    )
    fake_proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps({"result": "done"}),
        stderr="",
    )

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
    ):
        backend.execute(_make_spec(), _make_context())

    cmd = mock_run.call_args[0][0]
    assert "-q" in cmd
    assert "--full-auto" in cmd
    assert "--json" in cmd
