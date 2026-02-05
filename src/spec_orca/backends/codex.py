"""OpenAI Codex backend implementation."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import cast

from spec_orca.backend import Backend
from spec_orca.backends.codex_schema import render_codex_prompt
from spec_orca.git_ops import GitStatusDelta, compute_status_delta
from spec_orca.models import Context, Result, ResultStatus, Spec

__all__ = ["CodexBackend", "CodexConfig"]


_DEFAULT_TIMEOUT = 300
_DEFAULT_EXECUTABLE = "codex"

_ENV_EXECUTABLE = "CODEX_EXECUTABLE"
_ENV_TIMEOUT = "CODEX_TIMEOUT"
_ENV_MODEL = "CODEX_MODEL"


@dataclass(frozen=True)
class CodexConfig:
    """Configuration options for the Codex backend."""

    executable: str | None = None
    timeout: int | None = None
    model: str | None = None


class CodexBackend(Backend):
    """Backend that shells out to the OpenAI Codex CLI."""

    def __init__(self, config: CodexConfig | None = None) -> None:
        resolved = config or CodexConfig()
        env_executable = _read_env_value(_ENV_EXECUTABLE)
        env_timeout = _env_int(_ENV_TIMEOUT)
        env_model = _read_env_value(_ENV_MODEL)

        self._executable = resolved.executable or env_executable or _DEFAULT_EXECUTABLE
        self._timeout = (
            resolved.timeout if resolved.timeout is not None else (env_timeout or _DEFAULT_TIMEOUT)
        )
        self._model = resolved.model or env_model

    def execute(self, spec: Spec, context: Context) -> Result:
        pre_delta, pre_warning = compute_status_delta(context.repo_path)
        prompt = render_codex_prompt(spec, context)
        executable = self._resolve_executable()
        if executable is None:
            return _failure_result(
                "Codex CLI not found",
                (
                    f"Codex CLI not found: '{self._executable}'. "
                    "Install the OpenAI Codex CLI and ensure it is on PATH, "
                    "or set CODEX_EXECUTABLE to the full path."
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
                "Codex timed out",
                f"Codex timed out after {self._timeout} seconds.",
            )

        if proc.returncode != 0:
            output = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
            return _failure_result(
                "Codex exited with non-zero status",
                f"Codex failed (exit {proc.returncode}): {output}",
            )

        post_delta, post_warning = compute_status_delta(context.repo_path)
        response_text = _extract_result_text(proc.stdout)
        parsed = _parse_result_payload(response_text)
        if parsed is None:
            summary = response_text.strip() or "Codex completed successfully."
            parsed = Result(
                status=ResultStatus.SUCCESS,
                summary=summary,
                details="",
                files_changed=[],
                commands_run=[],
                error=None,
                structured_output=None,
            )

        files_changed, warning = _delta_files(pre_delta, post_delta, pre_warning, post_warning)
        details = parsed.details
        if warning:
            details = _merge_details_and_notes(details, [warning])
        return Result(
            status=parsed.status,
            summary=parsed.summary,
            details=details,
            files_changed=files_changed,
            commands_run=parsed.commands_run,
            error=parsed.error,
            structured_output=parsed.structured_output,
        )

    def _resolve_executable(self) -> str | None:
        return shutil.which(self._executable)

    def _build_command(self, executable: str, prompt: str) -> list[str]:
        cmd = [executable, "-q", "--full-auto", "--json"]
        if self._model:
            cmd.extend(["--model", self._model])
        cmd.append(prompt)
        return cmd


def _extract_result_text(raw_output: str) -> str:
    parsed = _parse_json_object(raw_output)
    if parsed is None:
        return raw_output.strip()
    result = parsed.get("result")
    if isinstance(result, str):
        return result.strip()
    return raw_output.strip()


def _parse_result_payload(response_text: str) -> Result | None:
    payload = _parse_json_object(response_text)
    if payload is None:
        return None

    status_raw = payload.get("status")
    summary = payload.get("summary")
    if not isinstance(status_raw, str) or not isinstance(summary, str) or not summary.strip():
        return None

    status = _to_result_status(status_raw)
    if status is None:
        return None

    details = payload.get("details", "")
    if not isinstance(details, str):
        details = ""

    commands_run = payload.get("commands_run", [])
    if not isinstance(commands_run, list) or not all(
        isinstance(item, str) for item in commands_run
    ):
        commands_run = []

    notes = payload.get("notes", [])
    if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
        notes = []
    details = _merge_details_and_notes(details, notes)

    error = payload.get("error")
    if error is not None and not isinstance(error, str):
        error = None

    return Result(
        status=status,
        summary=summary,
        details=details,
        files_changed=[],
        commands_run=commands_run,
        error=error,
        structured_output=payload,
    )


def _parse_json_object(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return cast(dict[str, object], parsed)
    return None


def _to_result_status(value: str) -> ResultStatus | None:
    lowered = value.strip().lower()
    if lowered == "success":
        return ResultStatus.SUCCESS
    if lowered == "partial":
        return ResultStatus.PARTIAL
    if lowered == "failure":
        return ResultStatus.FAILURE
    if lowered == "error":
        return ResultStatus.ERROR
    return None


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


def _env_int(key: str) -> int | None:
    raw = _read_env_value(key)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
