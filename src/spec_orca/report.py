"""Run-report generator -- converts an ExecutionSummary into Markdown."""

from __future__ import annotations

from datetime import UTC, datetime

from spec_orca.models import Context
from spec_orca.orchestrator import ExecutionSummary, RunStep


def _status_icon(status_value: str) -> str:
    """Return a Markdown-friendly icon for a result status."""
    icons: dict[str, str] = {
        "success": "pass",
        "partial": "partial",
        "failure": "FAIL",
        "error": "ERROR",
    }
    return icons.get(status_value, status_value)


def _render_results_table(step_details: list[RunStep]) -> str:
    """Render the results summary table."""
    lines: list[str] = [
        "| Step | Spec ID | Title | Status | Attempts |",
        "|------|---------|-------|--------|----------|",
    ]
    for step in step_details:
        status = _status_icon(step.result.status.value)
        lines.append(
            f"| {step.index + 1} | {step.spec_id} | {step.title} | {status} | {step.attempts} |"
        )
    return "\n".join(lines)


def _render_spec_details(step_details: list[RunStep]) -> str:
    """Render per-spec detail sections."""
    sections: list[str] = []
    for step in step_details:
        result = step.result
        parts: list[str] = [f"### {step.spec_id}: {step.title}"]
        parts.append("")
        parts.append(f"**Status:** {result.status.value}")
        parts.append("")
        parts.append(f"**Summary:** {result.summary}")

        if result.error:
            parts.append("")
            parts.append(f"**Error:** {result.error}")

        if result.files_changed:
            parts.append("")
            parts.append("**Files changed:**")
            for f in result.files_changed:
                parts.append(f"- `{f}`")

        sections.append("\n".join(parts))
    return "\n\n".join(sections)


def render_report(summary: ExecutionSummary, context: Context) -> str:
    """Render a Markdown run report from an execution summary and context.

    This is a pure function with no side effects.

    Args:
        summary: The completed execution summary.
        context: The run context (goal, backend, IDs, etc.).

    Returns:
        A Markdown-formatted report string.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    parts: list[str] = []

    # Top-level heading with goal
    parts.append(f"# {context.goal}")
    parts.append("")

    # Metadata section
    parts.append("## Metadata")
    parts.append("")
    parts.append(f"- **Backend:** {context.backend_name}")
    parts.append(f"- **Run ID:** {context.run_id}")
    parts.append(f"- **Max steps:** {context.max_steps}")
    parts.append(f"- **Timestamp:** {timestamp}")
    parts.append("")

    # Results table
    parts.append("## Results")
    parts.append("")
    parts.append(_render_results_table(summary.step_details))
    parts.append("")

    # Per-spec details
    parts.append("## Spec Details")
    parts.append("")
    parts.append(_render_spec_details(summary.step_details))
    parts.append("")

    # Totals and stopped reason
    parts.append("## Totals")
    parts.append("")
    parts.append(
        f"Completed: {summary.completed}, "
        f"Failed: {summary.failed}, "
        f"Pending: {summary.pending}, "
        f"In Progress: {summary.in_progress}"
    )
    parts.append("")
    parts.append(f"**Stopped reason:** {summary.stopped_reason}")
    parts.append("")

    return "\n".join(parts)
