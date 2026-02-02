"""Core data models for SpecOrca.

This module defines the typed dataclasses and enumerations used across
the orchestration system:

- **Spec-related**: SpecFormat, SpecStatus, Spec, Instruction
- **Result-related**: StepStatus, ResultStatus, StepResult, Result
- **Orchestration-related**: Context, OrchestratorState
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SpecFormat(enum.Enum):
    """Format of the source specification file."""

    MARKDOWN = "markdown"
    YAML = "yaml"


class SpecStatus(enum.Enum):
    """Lifecycle status of a specification."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepStatus(enum.Enum):
    """Outcome status of a single orchestration step."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class ResultStatus(enum.Enum):
    """Outcome status of a spec-level result (aggregated from steps)."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Spec-related models
# ---------------------------------------------------------------------------


def _generate_id() -> str:
    """Generate a short unique identifier."""
    return uuid.uuid4().hex[:12]


def _utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class Spec:
    """A loaded specification describing a unit of work."""

    title: str
    id: str = field(default_factory=_generate_id)
    description: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: SpecStatus = SpecStatus.PENDING
    attempts: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    source: Path | None = None
    format: SpecFormat | None = None
    raw_content: str = ""


@dataclass(frozen=True)
class Instruction:
    """A directive from the Architect to the Agent."""

    spec: Spec
    step_index: int
    prompt: str


# ---------------------------------------------------------------------------
# Result-related models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepResult:
    """Structured result returned by a backend after executing an instruction."""

    step_index: int
    status: StepStatus
    output: str
    summary: str = ""
    files_touched: tuple[str, ...] = ()
    commands_run: tuple[str, ...] = ()


@dataclass(frozen=True)
class Result:
    """Aggregated outcome of executing a spec (may span multiple steps).

    While StepResult captures a single backend invocation, Result captures
    the overall outcome of working on a Spec — including summary, files
    changed, commands run, and optional error context.
    """

    status: ResultStatus
    summary: str
    details: str = ""
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Orchestration-related models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Context:
    """Immutable context for an orchestration run.

    Captures the environment and configuration under which the orchestration
    loop executes.  Passed to the Architect and Agent so they can make
    informed decisions.
    """

    repo_path: Path
    spec_path: Path
    goal: str
    backend_name: str
    run_id: str = field(default_factory=_generate_id)
    step: int = 0
    max_steps: int = 1


@dataclass
class OrchestratorState:
    """Mutable state accumulator for the orchestration loop."""

    spec: Spec
    max_steps: int
    current_step: int = 0
    history: list[StepResult] = field(default_factory=list)
    done: bool = False


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "Context",
    "Instruction",
    "OrchestratorState",
    "Result",
    "ResultStatus",
    "Spec",
    "SpecFormat",
    "SpecStatus",
    "StepResult",
    "StepStatus",
]
