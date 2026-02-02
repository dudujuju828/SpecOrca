"""Pluggable backend implementations and registry.

Backend selection precedence (highest to lowest):
    1. CLI flag: ``--backend claude|mock``
    2. Environment variable: ``SPEC_ORCHESTRATOR_BACKEND``
    3. Default: ``mock``
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from spec_orchestrator.models import Instruction, StepResult, StepStatus

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_BACKEND_NAMES = ("claude", "mock")

_ENV_VAR = "SPEC_ORCHESTRATOR_BACKEND"
_DEFAULT_BACKEND = "mock"


def resolve_backend_name(cli_value: str | None = None) -> str:
    """Return the effective backend name after applying precedence rules.

    1. *cli_value* (explicit ``--backend`` flag)
    2. ``SPEC_ORCHESTRATOR_BACKEND`` environment variable
    3. Default (``mock``)
    """
    name = cli_value or os.environ.get(_ENV_VAR) or _DEFAULT_BACKEND
    name = name.strip().lower()
    if name not in _BACKEND_NAMES:
        msg = f"Unknown backend '{name}'. Available backends: {', '.join(_BACKEND_NAMES)}"
        raise ValueError(msg)
    return name


def create_backend(
    name: str,
    *,
    claude_executable: str | None = None,
) -> MockBackend | ClaudeBackend:
    """Instantiate a backend by its registered name.

    Args:
        name: One of ``"claude"`` or ``"mock"``.
        claude_executable: Override the path to the ``claude`` CLI
            (only relevant when *name* is ``"claude"``).
    """
    if name == "mock":
        return MockBackend()
    if name == "claude":
        return ClaudeBackend(executable=claude_executable or "claude")
    msg = f"Unknown backend: {name}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------


class MockBackend:
    """Deterministic backend for testing — returns predictable outputs."""

    def execute(self, instruction: Instruction) -> StepResult:
        return StepResult(
            step_index=instruction.step_index,
            status=StepStatus.SUCCESS,
            output=f"[mock] executed: {instruction.prompt}",
            summary=f"Mock execution of step {instruction.step_index}",
            files_touched=(),
            commands_run=(),
        )


# ---------------------------------------------------------------------------
# Claude Code backend
# ---------------------------------------------------------------------------


class ClaudeCodeNotFoundError(RuntimeError):
    """Raised when the Claude Code CLI executable cannot be found."""


class ClaudeBackend:
    """Backend that shells out to the Claude Code CLI.

    The ``claude`` command is invoked as a subprocess with ``shell=False``
    for safety.  The executable path can be overridden via the constructor
    or the ``CLAUDE_CODE_EXECUTABLE`` environment variable.
    """

    _ENV_EXECUTABLE = "CLAUDE_CODE_EXECUTABLE"

    def __init__(self, executable: str = "claude") -> None:
        self._executable = os.environ.get(self._ENV_EXECUTABLE, executable)

    # -- public interface ---------------------------------------------------

    def execute(self, instruction: Instruction) -> StepResult:
        self._ensure_executable()
        return self._run(instruction)

    # -- internals ----------------------------------------------------------

    def _ensure_executable(self) -> None:
        """Validate that the configured executable is on PATH."""
        if shutil.which(self._executable) is None:
            msg = (
                f"Claude Code CLI not found: '{self._executable}'. "
                "Install it (see https://docs.anthropic.com/en/docs/claude-code) "
                "or set CLAUDE_CODE_EXECUTABLE to the correct path."
            )
            raise ClaudeCodeNotFoundError(msg)

    def _run(self, instruction: Instruction) -> StepResult:
        """Shell out to the Claude Code CLI and parse the result."""
        cmd = [
            self._executable,
            "--print",
            "--output-format",
            "json",
            instruction.prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                step_index=instruction.step_index,
                status=StepStatus.ERROR,
                output="Claude Code timed out after 300 seconds.",
            )

        if proc.returncode != 0:
            return StepResult(
                step_index=instruction.step_index,
                status=StepStatus.FAILURE,
                output=proc.stderr or proc.stdout or f"Exit code {proc.returncode}",
            )

        return self._parse_output(instruction.step_index, proc.stdout)

    @staticmethod
    def _parse_output(step_index: int, raw: str) -> StepResult:
        """Parse Claude Code JSON output into a StepResult."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: treat the entire output as plain text.
            return StepResult(
                step_index=step_index,
                status=StepStatus.SUCCESS,
                output=raw.strip(),
                summary=raw.strip()[:200],
            )

        # Claude Code --output-format json returns a result object.
        if isinstance(data, dict):
            output = data.get("result", raw)
            return StepResult(
                step_index=step_index,
                status=StepStatus.SUCCESS,
                output=str(output),
                summary=str(output)[:200],
            )

        # If the response is a list (message blocks), join text blocks.
        if isinstance(data, list):
            texts: list[str] = []
            for block in data:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(str(block.get("text", "")))
            combined = "\n".join(texts) if texts else raw
            return StepResult(
                step_index=step_index,
                status=StepStatus.SUCCESS,
                output=combined,
                summary=combined[:200],
            )

        return StepResult(
            step_index=step_index,
            status=StepStatus.SUCCESS,
            output=raw.strip(),
            summary=raw.strip()[:200],
        )
