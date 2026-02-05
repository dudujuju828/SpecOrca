"""Backend implementations and selection helpers."""

from __future__ import annotations

from spec_orca.backends.claude import ClaudeCodeBackend, ClaudeCodeConfig
from spec_orca.backends.codex import CodexBackend, CodexConfig
from spec_orca.backends.mock import MockBackend, MockBackendConfig

__all__ = [
    "ClaudeBackend",
    "ClaudeCodeBackend",
    "ClaudeCodeConfig",
    "CodexBackend",
    "CodexConfig",
    "MockBackend",
    "MockBackendConfig",
    "create_backend",
    "resolve_backend_name",
]

_BACKEND_NAMES = ("claude", "codex", "mock")

_ENV_VAR = "SPEC_ORCA_BACKEND"
_DEFAULT_BACKEND = "mock"

# Backwards-compatible alias.
ClaudeBackend = ClaudeCodeBackend


def resolve_backend_name(cli_value: str | None = None) -> str:
    """Return the effective backend name after applying precedence rules."""
    import os

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
    claude_config: ClaudeCodeConfig | None = None,
    codex_executable: str | None = None,
    codex_config: CodexConfig | None = None,
    mock_config: MockBackendConfig | None = None,
) -> MockBackend | ClaudeCodeBackend | CodexBackend:
    """Instantiate a backend by its registered name."""
    if name == "mock":
        return MockBackend(config=mock_config)
    if name == "claude":
        claude_backend_config = claude_config or ClaudeCodeConfig(executable=claude_executable)
        return ClaudeCodeBackend(config=claude_backend_config)
    if name == "codex":
        codex_backend_config = codex_config or CodexConfig(executable=codex_executable)
        return CodexBackend(config=codex_backend_config)
    msg = f"Unknown backend: {name}"
    raise ValueError(msg)
