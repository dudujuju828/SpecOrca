"""Claude Code structured output schema and prompt template."""

from __future__ import annotations

from typing import Any

from spec_orca.models import Context, Spec

__all__ = ["STRUCTURED_SCHEMA", "render_prompt"]

STRUCTURED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "structured_output": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["success", "failure", "partial"],
                },
                "summary": {"type": "string"},
                "details": {"type": "string"},
                "commands_run": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "notes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "error": {"type": ["string", "null"]},
            },
            "required": ["status", "summary", "details", "commands_run", "notes", "error"],
            "additionalProperties": False,
        }
    },
    "required": ["structured_output"],
    "additionalProperties": True,
}


def render_prompt(spec: Spec, context: Context) -> str:
    """Render a stable prompt that instructs Claude to return structured output."""
    lines = [
        "You are implementing a spec in a git repository.",
        "Constraints:",
        f"- Repo root: {context.repo_path}",
        "- Only modify files inside the repo.",
        "- Do not introduce unrelated changes.",
        "",
        "Spec:",
        f"- ID: {spec.id}",
        f"- Title: {spec.title}",
    ]
    if spec.description:
        lines.append(f"- Description: {spec.description}")
    lines.append("Acceptance Criteria (verbatim):")
    if spec.acceptance_criteria:
        lines.extend(f"- {item}" for item in spec.acceptance_criteria)
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "Instructions:",
            "- Implement the spec.",
            "- If acceptance criteria mention tests or linting, run the relevant checks.",
            "- Return JSON that conforms to the provided JSON Schema.",
        ]
    )
    return "\n".join(lines)
