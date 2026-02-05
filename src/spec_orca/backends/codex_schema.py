"""Prompt helpers for the Codex backend."""

from __future__ import annotations

from spec_orca.backends.claude_schema import render_prompt
from spec_orca.models import Context, Spec

__all__ = ["render_codex_prompt"]

_SCHEMA_INSTRUCTION = "- Return JSON that conforms to the provided JSON Schema."


def render_codex_prompt(spec: Spec, context: Context) -> str:
    """Render the shared prompt, minus Claude-only schema instructions."""
    lines = render_prompt(spec, context).splitlines()
    filtered = [line for line in lines if line.strip() != _SCHEMA_INSTRUCTION]
    return "\n".join(filtered)
