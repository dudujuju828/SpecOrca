"""Claude Code backend implementation."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import overload

from spec_orca.models import (
    Context,
    Instruction,
    Result,
    ResultStatus,
    Spec,
    StepResult,
    StepStatus,
)

__all__ = ["ClaudeCodeBackend", "ClaudeCodeNotFoundError"]


class ClaudeCodeNotFoundError(RuntimeError):
    """Raised when the Claude Code CLI executable cannot be found."""


@dataclass(frozen=True)
class _RunOutput:
    status: ResultStatus
    output: str
    summary: str
    error: str | None


class ClaudeCodeBackend:
    """Backend that shells out to the Claude Code CLI.

    Default executable: "claude". Override with the CLAUDE_CODE_EXECUTABLE
    environment variable or the constructor's *executable* argument.
    """

    _ENV_EXECUTABLE = "CLAUDE_CODE_EXECUTABLE"
    _DEFAULT_EXECUTABLE = "claude"

    def __init__(self, executable: str | None = None, *, timeout: int = 300) -> None:
        env_value = _read_env_value(self._ENV_EXECUTABLE)
        self._executable = env_value or executable or self._DEFAULT_EXECUTABLE
        self._timeout = timeout

    @overload
    def execute(self, instruction: Instruction) -> StepResult: ...

    @overload
    def execute(self, spec: Spec, context: Context) -> Result: ...

    def execute(self, *args: object, **kwargs: object) -> Result | StepResult:
        if args:
            first = args[0]
            if isinstance(first, Instruction):
                if len(args) != 1:
                    msg = "execute(instruction) accepts exactly one positional argument"
                    raise TypeError(msg)
                return self._execute_instruction(first)
            if isinstance(first, Spec):
                if len(args) < 2 or not isinstance(args[1], Context):
                    msg = "execute(spec, context) requires a Context as the second argument"
                    raise TypeError(msg)
                return self._execute_spec(first, args[1])
        if "spec" in kwargs and "context" in kwargs:
            spec = kwargs.get("spec")
            context = kwargs.get("context")
            if not isinstance(spec, Spec) or not isinstance(context, Context):
                msg = "execute(spec, context) requires a Spec and Context"
                raise TypeError(msg)
            return self._execute_spec(spec, context)
        msg = "execute() requires either (instruction) or (spec, context)"
        raise TypeError(msg)

    def _execute_instruction(self, instruction: Instruction) -> StepResult:
        prompt = instruction.prompt
        output = self._run(prompt)
        if output.status == ResultStatus.ERROR:
            return StepResult(
                step_index=instruction.step_index,
                status=StepStatus.ERROR,
                output=output.output,
                summary=output.summary,
            )
        if output.status == ResultStatus.FAILURE:
            return StepResult(
                step_index=instruction.step_index,
                status=StepStatus.FAILURE,
                output=output.output,
                summary=output.summary,
            )
        return StepResult(
            step_index=instruction.step_index,
            status=StepStatus.SUCCESS,
            output=output.output,
            summary=output.summary,
        )

    def _execute_spec(self, spec: Spec, context: Context) -> Result:
        prompt = _render_spec_prompt(spec, context)
        output = self._run(prompt)
        return Result(
            status=output.status,
            summary=output.summary,
            details="",
            files_changed=[],
            commands_run=[],
            error=output.error,
        )

    def _run(self, prompt: str) -> _RunOutput:
        executable = self._resolve_executable()
        cmd = [
            executable,
            "--print",
            "--output-format",
            "json",
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            return _RunOutput(
                status=ResultStatus.ERROR,
                output=f"Claude Code timed out after {self._timeout} seconds.",
                summary="Claude Code timed out.",
                error="timeout",
            )

        if proc.returncode != 0:
            output = proc.stderr or proc.stdout or f"Exit code {proc.returncode}"
            return _RunOutput(
                status=ResultStatus.FAILURE,
                output=output.strip(),
                summary=output.strip()[:200],
                error=output.strip(),
            )

        parsed_output, summary = _parse_output(proc.stdout)
        return _RunOutput(
            status=ResultStatus.SUCCESS,
            output=parsed_output,
            summary=summary,
            error=None,
        )

    def _resolve_executable(self) -> str:
        env_value = _read_env_value(self._ENV_EXECUTABLE)
        executable = env_value or self._executable
        if shutil.which(executable) is None:
            msg = (
                f"Claude Code CLI not found: '{executable}'. "
                "Install it (see https://docs.anthropic.com/en/docs/claude-code) "
                "or set CLAUDE_CODE_EXECUTABLE to the correct path."
            )
            raise ClaudeCodeNotFoundError(msg)
        return executable


def _parse_output(raw: str) -> tuple[str, str]:
    """Parse Claude Code JSON output into an output+summary tuple."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        return cleaned, cleaned[:200]

    if isinstance(data, dict):
        output = data.get("result", raw)
        output_text = str(output)
        return output_text, output_text[:200]

    if isinstance(data, list):
        texts: list[str] = []
        for block in data:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text", "")))
        combined = "\n".join(texts) if texts else raw
        combined = combined.strip()
        return combined, combined[:200]

    cleaned = str(data).strip()
    return cleaned, cleaned[:200]


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
