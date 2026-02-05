"""Tests for the pluggable backend system."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from spec_orca.backends import (
    ClaudeBackend,
    ClaudeCodeConfig,
    CodexBackend,
    CodexConfig,
    MockBackend,
    MockBackendConfig,
    create_backend,
    resolve_backend_name,
)
from spec_orca.git_ops import GitStatusDelta
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
        assert resolve_backend_name("Codex") == "codex"

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

    def test_creates_codex(self) -> None:
        backend = create_backend("codex")
        assert isinstance(backend, CodexBackend)

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
    @pytest.fixture(autouse=True)
    def _stub_git_delta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "spec_orca.backends.claude.compute_status_delta",
            lambda *_args, **_kwargs: (GitStatusDelta(changed=[]), None),
        )

    def test_satisfies_protocol(self) -> None:
        assert isinstance(ClaudeBackend(), AgentBackendProtocol)

    def test_returns_failure_when_executable_missing(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="nonexistent-binary-xyz"))
        result = backend.execute(_make_spec(), _make_context())
        assert result.status == ResultStatus.FAILURE
        assert "not found" in (result.error or "").lower()

    def test_error_message_is_actionable(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="nonexistent-binary-xyz"))
        result = backend.execute(_make_spec(), _make_context())
        assert "CLAUDE_CODE_EXECUTABLE" in (result.error or "")

    def test_error_message_includes_install_url(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="nonexistent-binary-xyz"))
        result = backend.execute(_make_spec(), _make_context())
        assert "docs.anthropic.com" in (result.error or "")

    def test_successful_structured_output(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        json_output = json.dumps(
            {
                "structured_output": {
                    "status": "success",
                    "summary": "All done.",
                    "details": "ok",
                    "commands_run": ["pytest"],
                    "notes": ["note one"],
                    "error": None,
                }
            }
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.SUCCESS
        assert result.summary == "All done."
        assert result.commands_run == ["pytest"]
        assert result.structured_output is not None

    def test_nonzero_exit_code(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="something broke"
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "something broke" in (result.error or "")

    def test_nonzero_exit_fallback_to_stdout(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="stdout msg", stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "stdout msg" in (result.error or "")

    def test_nonzero_exit_fallback_to_exit_code(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        fake_proc = subprocess.CompletedProcess(args=[], returncode=42, stdout="", stderr="")

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "42" in (result.error or "")

    def test_timeout_returns_error(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired("claude", 300),
            ),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "timed out" in (result.error or "").lower()

    def test_env_var_overrides_executable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_CODE_EXECUTABLE", "/custom/path/claude")
        backend = ClaudeBackend(ClaudeCodeConfig(executable=None))
        assert backend._executable == "/custom/path/claude"

    def test_no_shell_true(self) -> None:
        """Verify subprocess.run is called without shell=True."""
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        json_output = json.dumps(
            {
                "structured_output": {
                    "status": "success",
                    "summary": "ok",
                    "details": "",
                    "commands_run": [],
                    "notes": [],
                    "error": None,
                }
            }
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            backend.execute(_make_spec(), _make_context())

        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("shell") is not True

    def test_invalid_json_returns_failure(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="{bad json", stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "invalid json" in (result.error or "").lower()

    def test_missing_structured_output_synthesizes_success(self) -> None:
        """When structured_output is absent but no errors, treat as success."""
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"foo": "bar"}), stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.SUCCESS

    def test_missing_structured_output_with_errors_returns_failure(self) -> None:
        """When structured_output is absent and errors are present, fail."""
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        envelope = {"is_error": True, "errors": ["something went wrong"], "num_turns": 5}
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(envelope), stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE

    def test_passes_prompt_as_argument(self) -> None:
        """The spec prompt should be passed as a CLI argument."""
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        json_output = json.dumps(
            {
                "structured_output": {
                    "status": "success",
                    "summary": "ok",
                    "details": "",
                    "commands_run": [],
                    "notes": [],
                    "error": None,
                }
            }
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            backend.execute(_make_spec(), _make_context())

        cmd = mock_run.call_args[0][0]
        assert "Title: Test Spec" in " ".join(cmd)

    def test_includes_required_flags_and_cwd(self) -> None:
        backend = ClaudeBackend(
            ClaudeCodeConfig(
                executable="claude",
                allowed_tools=["read:*"],
                disallowed_tools=["rm:*"],
                tools=["edit"],
                max_turns=2,
                max_budget_usd=1.5,
                no_session_persistence=True,
                timeout=10,
            )
        )
        json_output = json.dumps(
            {
                "structured_output": {
                    "status": "success",
                    "summary": "ok",
                    "details": "",
                    "commands_run": [],
                    "notes": [],
                    "error": None,
                }
            }
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            backend.execute(_make_spec(), _make_context())

        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--json-schema" in cmd
        assert "--allowedTools" in cmd
        assert "--disallowedTools" in cmd
        assert "--tools" in cmd
        assert "--max-turns" in cmd
        assert "--max-budget-usd" in cmd
        assert "--no-session-persistence" in cmd
        assert mock_run.call_args.kwargs.get("cwd") == _make_context().repo_path

    def test_allowed_tools_are_passed_as_separate_args(self) -> None:
        backend = ClaudeBackend(
            ClaudeCodeConfig(
                executable="claude",
                allowed_tools=["read:*", "write:*"],
                timeout=10,
            )
        )
        json_output = json.dumps(
            {
                "structured_output": {
                    "status": "success",
                    "summary": "ok",
                    "details": "",
                    "commands_run": [],
                    "notes": [],
                    "error": None,
                }
            }
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            backend.execute(_make_spec(), _make_context())

        cmd = mock_run.call_args[0][0]
        allowed_index = cmd.index("--allowedTools")
        assert cmd[allowed_index + 1] == "read:*,write:*"
        assert "--json-schema" in cmd
        schema_index = cmd.index("--json-schema")
        assert cmd[schema_index + 1].startswith("{")
        assert cmd[schema_index + 1].endswith("}")

    def test_invalid_structured_output_returns_failure(self) -> None:
        backend = ClaudeBackend(ClaudeCodeConfig(executable="claude"))
        json_output = json.dumps(
            {
                "structured_output": {
                    "status": "unknown",
                    "summary": "bad",
                    "details": "",
                    "commands_run": [],
                    "notes": [],
                    "error": None,
                }
            }
        )
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json_output, stderr=""
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/claude"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "structured_output.status" in (result.error or "")


class TestCodexBackend:
    @pytest.fixture(autouse=True)
    def _stub_git_delta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "spec_orca.backends.codex.compute_status_delta",
            lambda *_args, **_kwargs: (GitStatusDelta(changed=[]), None),
        )

    def test_satisfies_protocol(self) -> None:
        assert isinstance(CodexBackend(), AgentBackendProtocol)

    def test_returns_failure_when_executable_missing(self) -> None:
        backend = CodexBackend(CodexConfig(executable="nonexistent-codex-xyz"))

        result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.FAILURE
        assert "not found" in (result.error or "").lower()
        assert "CODEX_EXECUTABLE" in (result.error or "")

    def test_builds_expected_command(self) -> None:
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
        assert "--model" in cmd
        model_index = cmd.index("--model")
        assert cmd[model_index + 1] == "gpt-5-codex"
        assert mock_run.call_args.kwargs.get("cwd") == _make_context().repo_path
        assert mock_run.call_args.kwargs.get("shell") is not True

    def test_exit_zero_with_plain_text_result_is_success(self) -> None:
        backend = CodexBackend(CodexConfig(executable="codex"))
        fake_proc = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"result": "Implemented spec successfully."}),
            stderr="",
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/codex"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.SUCCESS
        assert result.summary == "Implemented spec successfully."
        assert result.error is None

    def test_exit_zero_with_structured_json_in_result_is_mapped(self) -> None:
        backend = CodexBackend(CodexConfig(executable="codex"))
        fake_proc = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "result": json.dumps(
                        {
                            "status": "partial",
                            "summary": "Half done.",
                            "details": "Need one more step.",
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

        assert result.status == ResultStatus.PARTIAL
        assert result.summary == "Half done."
        assert result.commands_run == ["pytest"]
        assert result.structured_output is not None

    def test_exit_zero_with_non_json_stdout_is_success(self) -> None:
        backend = CodexBackend(CodexConfig(executable="codex"))
        fake_proc = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="plain response text",
            stderr="",
        )

        with (
            mock.patch("shutil.which", return_value="/usr/bin/codex"),
            mock.patch("subprocess.run", return_value=fake_proc),
        ):
            result = backend.execute(_make_spec(), _make_context())

        assert result.status == ResultStatus.SUCCESS
        assert result.summary == "plain response text"

    def test_nonzero_exit_is_failure(self) -> None:
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

    def test_timeout_returns_failure(self) -> None:
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
