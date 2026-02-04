"""Claude Code backend implementation."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from spec_orca.backend import Backend
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

_STRUCTURED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "structured_output": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["success", "partial", "failure", "error"],
                },
                "summary": {"type": "string"},
                "details": {"type": "string"},
                "files_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "commands_run": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "error": {"type": ["string", "null"]},
            },
            "required": ["status", "summary"],
            "additionalProperties": False,
        }
    },
    "required": ["structured_output"],
    "additionalProperties": True,
}


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
    timeout: int = _DEFAULT_TIMEOUT


class ClaudeCodeBackend(Backend):
    """Backend that shells out to the Claude Code CLI."""

    def __init__(self, config: ClaudeCodeConfig | None = None) -> None:
        resolved = config or ClaudeCodeConfig()
        env_executable = _read_env_value(_ENV_EXECUTABLE)
        self._executable = env_executable or resolved.executable or _DEFAULT_EXECUTABLE
        self._allowed_tools = _env_list(_ENV_ALLOWED_TOOLS) or resolved.allowed_tools
        self._disallowed_tools = _env_list(_ENV_DISALLOWED_TOOLS) or resolved.disallowed_tools
        self._tools = _env_list(_ENV_TOOLS) or resolved.tools
        self._max_turns = _env_int(_ENV_MAX_TURNS) or resolved.max_turns
        self._max_budget_usd = _env_float(_ENV_MAX_BUDGET) or resolved.max_budget_usd
        self._timeout = _env_int(_ENV_TIMEOUT) or resolved.timeout
        env_no_session = _env_bool(_ENV_NO_SESSION)
        self._no_session_persistence = (
            env_no_session if env_no_session is not None else resolved.no_session_persistence
        )

    def execute(self, spec: Spec, context: Context) -> Result:
        prompt = _render_spec_prompt(spec, context)
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

        parsed = _parse_json(proc.stdout)
        if isinstance(parsed, str):
            return _failure_result("Claude Code returned invalid JSON", parsed)

        structured = parsed.get("structured_output")
        if not isinstance(structured, dict):
            return _failure_result(
                "Claude Code returned missing structured output",
                "Expected JSON output with a 'structured_output' object.",
            )

        result = _result_from_structured(structured)
        if isinstance(result, str):
            return _failure_result("Claude Code returned invalid structured output", result)
        return result

    def _resolve_executable(self) -> str | None:
        return shutil.which(self._executable)

    def _build_command(self, executable: str, prompt: str) -> list[str]:
        cmd = [
            executable,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(_STRUCTURED_SCHEMA, separators=(",", ":")),
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
    try:
        status = ResultStatus(status_raw)
    except ValueError:
        return "structured_output.status must be one of: success, partial, failure, error"

    summary = structured.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return "structured_output.summary must be a non-empty string"

    details = structured.get("details", "")
    if not isinstance(details, str):
        return "structured_output.details must be a string"

    files_changed = structured.get("files_changed", [])
    if not isinstance(files_changed, list) or not all(
        isinstance(item, str) for item in files_changed
    ):
        return "structured_output.files_changed must be a list of strings"

    commands_run = structured.get("commands_run", [])
    if not isinstance(commands_run, list) or not all(
        isinstance(item, str) for item in commands_run
    ):
        return "structured_output.commands_run must be a list of strings"

    error = structured.get("error")
    if error is not None and not isinstance(error, str):
        return "structured_output.error must be a string or null"

    return Result(
        status=status,
        summary=summary,
        details=details,
        files_changed=files_changed,
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


def _render_spec_prompt(spec: Spec, context: Context) -> str:
    """Create a deterministic prompt from spec and context."""
    lines = [
        f"Goal: {context.goal}",
        f"Spec ID: {spec.id}",
        f"Title: {spec.title}",
    ]
    if spec.description:
        lines.append(f"Description: {spec.description}")
    if spec.acceptance_criteria:
        lines.append("Acceptance Criteria:")
        lines.extend(f"- {item}" for item in spec.acceptance_criteria)
    if spec.dependencies:
        lines.append("Dependencies:")
        lines.extend(f"- {item}" for item in spec.dependencies)
    return "\n".join(lines)


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
