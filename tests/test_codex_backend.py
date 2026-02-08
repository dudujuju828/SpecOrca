"""Tests for the Codex backend adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from spec_orca.backends.codex import CodexBackend, CodexConfig
from spec_orca.git_ops import GitStatusDelta
from spec_orca.models import Context, ResultStatus, Spec


def _make_spec() -> Spec:
    return Spec(
        id="codex-step",
        title="Implement codex backend",
        description="Wire codex exec for non-interactive runs.",
        acceptance_criteria=["Run codex in JSON mode."],
    )


def _make_context(tmp_path: Path) -> Context:
    return Context(
        repo_path=tmp_path,
        spec_path=tmp_path / "spec.yaml",
        goal="Ship codex backend",
        backend_name="codex",
    )


@pytest.fixture(autouse=True)
def _stub_git_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "spec_orca.backends.codex.compute_status_delta",
        lambda *_args, **_kwargs: (GitStatusDelta(changed=[]), None),
    )


def _completed(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_success_with_json_response(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))
    response = {
        "status": "success",
        "summary": "Completed.",
        "details": "done",
        "commands_run": ["pytest -q"],
        "notes": ["left a TODO"],
        "error": None,
    }
    payload = json.dumps({"result": json.dumps(response)})

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=_completed(stdout=payload)),
    ):
        result = backend.execute(_make_spec(), _make_context(tmp_path))

    assert result.status == ResultStatus.SUCCESS
    assert result.summary == "Completed."
    assert result.commands_run == ["pytest -q"]
    assert result.structured_output is not None


def test_success_with_plain_text_response(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))
    payload = json.dumps({"result": "Implemented successfully"})

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=_completed(stdout=payload)),
    ):
        result = backend.execute(_make_spec(), _make_context(tmp_path))

    assert result.status == ResultStatus.SUCCESS
    assert result.summary == "Implemented successfully"
    assert result.structured_output is None


def test_non_zero_exit_returns_failure(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch(
            "subprocess.run",
            return_value=_completed(returncode=2, stderr="unexpected argument"),
        ),
    ):
        result = backend.execute(_make_spec(), _make_context(tmp_path))

    assert result.status == ResultStatus.FAILURE
    assert "exit 2" in (result.error or "").lower()


def test_timeout_returns_failure(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex", timeout=12))

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("codex", 12),
        ),
    ):
        result = backend.execute(_make_spec(), _make_context(tmp_path))

    assert result.status == ResultStatus.FAILURE
    assert "timed out" in (result.error or "").lower()


def test_command_includes_exec_full_auto_and_json(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex", model="gpt-5-codex", timeout=30))
    payload = json.dumps({"result": "ok"})

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=_completed(stdout=payload)) as mocked_run,
    ):
        backend.execute(_make_spec(), _make_context(tmp_path))

    cmd = mocked_run.call_args[0][0]
    assert cmd[:4] == ["/usr/bin/codex", "exec", "--full-auto", "--json"]
    assert "--model" in cmd
    assert "-q" not in cmd
    assert mocked_run.call_args.kwargs["cwd"] == _make_context(tmp_path).repo_path


def test_missing_executable_returns_failure(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="missing-codex"))

    with mock.patch("shutil.which", return_value=None):
        result = backend.execute(_make_spec(), _make_context(tmp_path))

    assert result.status == ResultStatus.FAILURE
    assert "CODEX_EXECUTABLE" in (result.error or "")


def test_chat_returns_text(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch(
            "subprocess.run",
            return_value=_completed(stdout="  Conversational reply  "),
        ),
    ):
        result = backend.chat("hello", cwd=tmp_path)

    assert result == "Conversational reply"


def test_chat_no_json_flag(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch(
            "subprocess.run",
            return_value=_completed(stdout="ok"),
        ) as mocked_run,
    ):
        backend.chat("hello", cwd=tmp_path)

    cmd = mocked_run.call_args[0][0]
    assert "--json" not in cmd
    assert "exec" in cmd
    assert "--full-auto" in cmd


def test_chat_missing_executable() -> None:
    backend = CodexBackend(CodexConfig(executable="missing-codex"))

    with mock.patch("shutil.which", return_value=None):
        result = backend.chat("hi")

    assert result.startswith("Error:")
    assert "not found" in result.lower()


def test_chat_timeout(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex", timeout=10))

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("codex", 10),
        ),
    ):
        result = backend.chat("hi", cwd=tmp_path)

    assert result.startswith("Error:")
    assert "timed out" in result.lower()


def test_success_with_jsonl_event_stream(tmp_path: Path) -> None:
    backend = CodexBackend(CodexConfig(executable="codex"))
    response = {
        "status": "success",
        "summary": "From event stream.",
        "details": "",
        "commands_run": [],
        "notes": [],
        "error": None,
    }
    payload = "\n".join(
        [
            json.dumps({"type": "session.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": json.dumps(response),
                    },
                }
            ),
        ]
    )

    with (
        mock.patch("shutil.which", return_value="/usr/bin/codex"),
        mock.patch("subprocess.run", return_value=_completed(stdout=payload)),
    ):
        result = backend.execute(_make_spec(), _make_context(tmp_path))

    assert result.status == ResultStatus.SUCCESS
    assert result.summary == "From event stream."
