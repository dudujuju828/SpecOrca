"""Claude Code backend implementation."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from spec_orca.backend import Backend
from spec_orca.backends.claude_schema import STRUCTURED_SCHEMA, render_prompt
from spec_orca.git_ops import GitStatusDelta, compute_status_delta
from spec_orca.models import Context, Result, ResultStatus, Spec

__all__ = ["ClaudeCodeBackend", "ClaudeCodeConfig"]


_DEFAULT_TIMEOUT = 300
_DEFAULT_EXECUTABLE = "claude"

_ENV_EXECUTABLE = "CLAUDE_CODE_EXECUTABLE"
_ENV_ALLOWED_TOOLS = "CLAUDE_CODE_ALLOWED_TOOLS"
_ENV_DISALLOWED_TOOLS = "CLAUDE_CODE_DISALLOWED_TOOLS"
_ENV_TOOLS = "CLAUDE_CODE_TOOLS"
_ENV_MAX_TURNS = "CLAUDE_CODE_MAX_TURNS"
_ENV_MAX_BUDGET = "CLAUDE_CODE_MAX_BUDGET_USD"
_ENV_TIMEOUT = "CLAUDE_CODE_TIMEOUT"
_ENV_NO_SESSION = "CLAUDE_CODE_NO_SESSION_PERSISTENCE"


@dataclass(frozen=True)
class ClaudeCodeConfig:
    """Configuration options for the Claude Code backend."""

    executable: str | None = None
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    tools: list[str] | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    no_session_persistence: bool = True
    timeout: int | None = None


class ClaudeCodeBackend(Backend):
    """Backend that shells out to the Claude Code CLI."""

    def __init__(self, config: ClaudeCodeConfig | None = None) -> None:
        resolved = config or ClaudeCodeConfig()
        env_executable = _read_env_value(_ENV_EXECUTABLE)
        self._executable = resolved.executable or env_executable or _DEFAULT_EXECUTABLE
        self._allowed_tools = resolved.allowed_tools or _env_list(_ENV_ALLOWED_TOOLS)
        self._disallowed_tools = resolved.disallowed_tools or _env_list(_ENV_DISALLOWED_TOOLS)
        self._tools = resolved.tools or _env_list(_ENV_TOOLS)
        self._max_turns = resolved.max_turns or _env_int(_ENV_MAX_TURNS)
        self._max_budget_usd = resolved.max_budget_usd or _env_float(_ENV_MAX_BUDGET)
        self._timeout = resolved.timeout or _env_int(_ENV_TIMEOUT) or _DEFAULT_TIMEOUT
        env_no_session = _env_bool(_ENV_NO_SESSION)
        self._no_session_persistence = (
            resolved.no_session_persistence
            if resolved.no_session_persistence is not None
            else (env_no_session if env_no_session is not None else True)
        )

    def execute(self, spec: Spec, context: Context) -> Result:
        pre_delta, pre_warning = compute_status_delta(context.repo_path)
        prompt = render_prompt(spec, context)
        executable = self._resolve_executable()
        if executable is None:
            return _failure_result(
                "Claude Code CLI not found",
                (
                    f"Claude Code CLI not found: '{self._executable}'. "
                    "Install it (see https://docs.anthropic.com/en/docs/claude-code) "
                    "or set CLAUDE_CODE_EXECUTABLE to the correct path."
                ),
            )

        cmd = self._build_command(executable, prompt)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=context.repo_path,
            )
        except subprocess.TimeoutExpired:
            return _failure_result(
                "Claude Code timed out",
                f"Claude Code timed out after {self._timeout} seconds.",
            )

        if proc.returncode != 0:
            output = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
            return _failure_result(
                "Claude Code exited with non-zero status",
                f"Claude Code failed (exit {proc.returncode}): {output}",
            )

        post_delta, post_warning = compute_status_delta(context.repo_path)
        parsed = _parse_json(proc.stdout)
        if isinstance(parsed, str):
            return _failure_result("Claude Code returned invalid JSON", parsed)

        structured = parsed.get("structured_output")
        if not isinstance(structured, dict):
            return _failure_result(
                "Claude Code returned missing structured output",
                "Expected JSON output with a 'structured_output' object.",
            )

        # The CLI envelope places the --json-schema response under
        # "structured_output", and the schema itself wraps fields in a
        # "structured_output" key, producing double nesting.  Unwrap it.
        if "structured_output" in structured and isinstance(
            structured["structured_output"], dict
        ):
            structured = structured["structured_output"]

        result = _result_from_structured(structured)
        if isinstance(result, str):
            return _failure_result("Claude Code returned invalid structured output", result)
        files_changed, warning = _delta_files(pre_delta, post_delta, pre_warning, post_warning)
        details = result.details
        if warning:
            details = _merge_details_and_notes(details, [warning])
        return Result(
            status=result.status,
            summary=result.summary,
            details=details,
            files_changed=files_changed,
            commands_run=result.commands_run,
            error=result.error,
            structured_output=result.structured_output,
        )

    def _resolve_executable(self) -> str | None:
        return shutil.which(self._executable)

    def _build_command(self, executable: str, prompt: str) -> list[str]:
        cmd = [
            executable,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(STRUCTURED_SCHEMA, separators=(",", ":")),
            prompt,
        ]
        if self._allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self._allowed_tools)])
        if self._disallowed_tools:
            cmd.extend(["--disallowedTools", ",".join(self._disallowed_tools)])
        if self._tools:
            cmd.extend(["--tools", ",".join(self._tools)])
        if self._max_turns is not None:
            cmd.extend(["--max-turns", str(self._max_turns)])
        if self._max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self._max_budget_usd)])
        if self._no_session_persistence:
            cmd.append("--no-session-persistence")
        return cmd


def _parse_json(raw: str) -> dict[str, Any] | str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON output: {str(exc).strip()}"
    if not isinstance(data, dict):
        return "Expected JSON object output from Claude Code."
    return data


def _result_from_structured(structured: dict[str, Any]) -> Result | str:
    status_raw = structured.get("status")
    if not isinstance(status_raw, str):
        return "structured_output.status must be a string"
    if status_raw == "success":
        status = ResultStatus.SUCCESS
    elif status_raw == "partial":
        status = ResultStatus.PARTIAL
    elif status_raw == "failure":
        status = ResultStatus.FAILURE
    else:
        return "structured_output.status must be one of: success, partial, failure"

    summary = structured.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return "structured_output.summary must be a non-empty string"

    details = structured.get("details", "")
    if not isinstance(details, str):
        return "structured_output.details must be a string"

    commands_run = structured.get("commands_run", [])
    if not isinstance(commands_run, list) or not all(
        isinstance(item, str) for item in commands_run
    ):
        return "structured_output.commands_run must be a list of strings"

    notes = structured.get("notes", [])
    if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
        return "structured_output.notes must be a list of strings"

    error = structured.get("error")
    if error is not None and not isinstance(error, str):
        return "structured_output.error must be a string or null"

    details = _merge_details_and_notes(details, notes)

    return Result(
        status=status,
        summary=summary,
        details=details,
        commands_run=commands_run,
        error=error,
        structured_output=structured,
    )


def _failure_result(summary: str, error: str) -> Result:
    return Result(
        status=ResultStatus.FAILURE,
        summary=summary,
        details="",
        files_changed=[],
        commands_run=[],
        error=error,
        structured_output=None,
    )


def _merge_details_and_notes(details: str, notes: list[str]) -> str:
    if not notes:
        return details
    notes_block = "\n".join(f"- {note}" for note in notes)
    if details.strip():
        return f"{details.rstrip()}\n\nNotes:\n{notes_block}"
    return f"Notes:\n{notes_block}"


def _delta_files(
    before: GitStatusDelta,
    after: GitStatusDelta,
    pre_warning: str | None,
    post_warning: str | None,
) -> tuple[list[str], str | None]:
    if pre_warning or post_warning:
        warning = pre_warning or post_warning
        return [], f"Git status unavailable: {warning}"
    changed = sorted(set(after.changed) - set(before.changed))
    return changed, None


def _read_env_value(key: str) -> str | None:
    import os

    value = os.environ.get(key)
    if value is None:
        return None
    return value.strip() or None


def _env_list(key: str) -> list[str] | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_int(key: str) -> int | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_float(key: str) -> float | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_bool(key: str) -> bool | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    return raw.lower() in {"1", "true", "yes", "on"}
