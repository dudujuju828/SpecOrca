"""Tests for the pluggable backend system."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from spec_orca.backends import (
    ClaudeBackend,
    ClaudeCodeNotFoundError,
    MockBackend,
    MockBackendConfig,
    create_backend,
    resolve_backend_name,
)
from spec_orca.models import (
    Context,
    Instruction,
    ResultStatus,
    Spec,
    SpecFormat,
    StepStatus,
)
from spec_orca.protocols import AgentBackendProtocol

# -- helpers ----------------------------------------------------------------


def _make_spec() -> Spec:
    return Spec(
        source=Path("/tmp/test.md"),
        format=SpecFormat.MARKDOWN,
        title="Test Spec",
        raw_content="# Test Spec\nContent.",
    )


def _make_instruction(step_index: int = 0, prompt: str = "do something") -> Instruction:
    return Instruction(spec=_make_spec(), step_index=step_index, prompt=prompt)


def _make_context() -> Context:
    return Context(
        repo_path=Path("/tmp"),
        spec_path=Path("/tmp/spec.md"),
        goal="test goal",
        backend_name="mock",
    )


# -- resolve_backend_name ---------------------------------------------------


class TestResolveBackendName:
    def test_cli_flag_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_ORCA_BACKEND", "claude")
        assert resolve_backend_name("mock") == "mock"

    def test_env_var_used_when_no_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_ORCA_BACKEND", "claude")
        assert resolve_backend_name(None) == "claude"

    def test_default_when_nothing_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_ORCA_BACKEND", raising=False)
        assert resolve_backend_name(None) == "mock"

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend 'nope'"):
            resolve_backend_name("nope")

    def test_case_insensitive(self) -> None:
        assert resolve_backend_name("MOCK") == "mock"
        assert resolve_backend_name("Claude") == "claude"

    def test_whitespace_stripped(self) -> None:
        assert resolve_backend_name("  mock  ") == "mock"


# -- create_backend ---------------------------------------------------------


class TestCreateBackend:
    def test_creates_mock(self) -> None:
        backend = create_backend("mock")
        assert isinstance(backend, MockBackend)

    def test_creates_claude(self) -> None:
        backend = create_backend("claude")
        assert isinstance(backend, ClaudeBackend)

    def test_creates_claude_with_executable(self) -> None:
        backend = create_backend("claude", claude_executable="/usr/local/bin/claude")
        assert isinstance(backend, ClaudeBackend)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            create_backend("bogus")


# -- MockBackend ------------------------------------------------------------


class TestMockBackend:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(MockBackend(), AgentBackendProtocol)

    def test_returns_success(self) -> None:
        result = MockBackend().execute(_make_instruction())
        assert result.status == StepStatus.SUCCESS

    def test_output_contains_prompt(self) -> None:
        result = MockBackend().execute(_make_instruction(prompt="build widgets"))
        assert "build widgets" in result.output

    def test_summary_populated(self) -> None:
        result = MockBackend().execute(_make_instruction(step_index=2))
        assert "step 2" in result.summary.lower()

    def test_deterministic(self) -> None:
        instr = _make_instruction()
        a = MockBackend().execute(instr)
        b = MockBackend().execute(instr)
        assert a == b

    def test_new_step_result_fields(self) -> None:
        result = MockBackend().execute(_make_instruction())
        assert isinstance(result.files_touched, tuple)
        assert isinstance(result.commands_run, tuple)

    def test_different_steps_different_summary(self) -> None:
        r0 = MockBackend().execute(_make_instruction(step_index=0))
        r1 = MockBackend().execute(_make_instruction(step_index=1))
        assert r0.summary != r1.summary

    def test_configurable_result_and_files(self) -> None:
        config = MockBackendConfig(
            status=ResultStatus.FAILURE,
            summary="Forced failure",
            files_changed=["a.txt", "b.txt"],
            commands_run=["pytest"],
            error="boom",
        )
        backend = MockBackend(config=config)

        result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert result.summary == "Forced failure"
        assert result.files_changed == ["a.txt", "b.txt"]
        assert result.commands_run == ["pytest"]
        assert result.error == "boom"

    def test_create_backend_uses_mock_config(self) -> None:
        config = MockBackendConfig(status=ResultStatus.ERROR, error="bad")
        backend = create_backend("mock", mock_config=config)

        result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.ERROR
        assert result.error == "bad"


# -- ClaudeBackend ----------------------------------------------------------


class TestClaudeBackend:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(ClaudeBackend(), AgentBackendProtocol)

    def test_raises_when_executable_missing(self) -> None:
        backend = ClaudeBackend(executable="nonexistent-binary-xyz")
        with pytest.raises(ClaudeCodeNotFoundError, match="not found"):
            backend.execute(_make_instruction())

    def test_error_message_is_actionable(self) -> None:
        backend = ClaudeBackend(executable="nonexistent-binary-xyz")
        with pytest.raises(ClaudeCodeNotFoundError, match="CLAUDE_CODE_EXECUTABLE"):
            backend.execute(_make_instruction())

    def test_error_message_includes_install_url(self) -> None:
        backend = ClaudeBackend(executable="nonexistent-binary-xyz")
        with pytest.raises(ClaudeCodeNotFoundError, match=r"docs\.anthropic\.com"):
            backend.execute(_make_instruction())

    def test_successful_json_dict(self) -> None:
        backend = ClaudeBackend(executable="claude")
        json_output = json.dumps({"result": "All done."})
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.SUCCESS
        assert "All done." in result.output

    def test_successful_json_list(self) -> None:
        backend = ClaudeBackend(executable="claude")
        json_output = json.dumps(
            [
                {"type": "text", "text": "First block."},
                {"type": "text", "text": "Second block."},
            ]
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.SUCCESS
        assert "First block." in result.output
        assert "Second block." in result.output

    def test_json_neither_dict_nor_list(self) -> None:
        """JSON that parses but is not dict/list (e.g. a string) uses fallback."""
        backend = ClaudeBackend(executable="claude")
        json_output = json.dumps("just a string")
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.SUCCESS
        assert "just a string" in result.output

    def test_json_integer_fallback(self) -> None:
        backend = ClaudeBackend(executable="claude")
        json_output = json.dumps(42)
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.SUCCESS
        assert "42" in result.output

    def test_plain_text_fallback(self) -> None:
        backend = ClaudeBackend(executable="claude")
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Just plain text.", stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.SUCCESS
        assert "Just plain text." in result.output

    def test_nonzero_exit_code(self) -> None:
        backend = ClaudeBackend(executable="claude")
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="something broke"
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.FAILURE
        assert "something broke" in result.output

    def test_nonzero_exit_fallback_to_stdout(self) -> None:
        backend = ClaudeBackend(executable="claude")
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="stdout msg", stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.FAILURE
        assert "stdout msg" in result.output

    def test_nonzero_exit_fallback_to_exit_code(self) -> None:
        backend = ClaudeBackend(executable="claude")
        fake_proc = subprocess.CompletedProcess(args=[], returncode=42, stdout="", stderr="")

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.FAILURE
        assert "42" in result.output

    def test_timeout_returns_error(self) -> None:
        backend = ClaudeBackend(executable="claude")

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired("claude", 300),
            ),
        ):
            result = backend.execute(_make_instruction())

        assert result.status == StepStatus.ERROR
        assert "timed out" in result.output.lower()

    def test_env_var_overrides_executable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_CODE_EXECUTABLE", "/custom/path/claude")
        backend = ClaudeBackend(executable="default")
        assert backend._executable == "/custom/path/claude"

    def test_no_shell_true(self) -> None:
        """Verify subprocess.run is called without shell=True."""
        backend = ClaudeBackend(executable="claude")
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr="")

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            backend.execute(_make_instruction())

        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("shell") is not True

    def test_summary_truncated_at_200(self) -> None:
        """Summary should be capped at 200 characters."""
        backend = ClaudeBackend(executable="claude")
        long_text = "A" * 500
        json_output = json.dumps({"result": long_text})
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_instruction())

        assert len(result.summary) == 200

    def test_passes_prompt_as_argument(self) -> None:
        """The instruction prompt should be passed as a CLI argument."""
        backend = ClaudeBackend(executable="claude")
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr="")

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            backend.execute(_make_instruction(prompt="do the thing"))

        cmd = mock_run.call_args[0][0]
        assert "do the thing" in cmd
