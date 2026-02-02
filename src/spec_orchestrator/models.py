"""Core data models for spec-orchestrator."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path


class SpecFormat(enum.Enum):
    """Format of the source specification file."""

    MARKDOWN = "markdown"
    YAML = "yaml"


class StepStatus(enum.Enum):
    """Outcome status of a single orchestration step."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


@dataclass(frozen=True)
class Spec:
    """A loaded specification describing a unit of work."""

    source: Path
    format: SpecFormat
    title: str
    raw_content: str


@dataclass(frozen=True)
class Instruction:
    """A directive from the Architect to the Agent."""

    spec: Spec
    step_index: int
    prompt: str


@dataclass(frozen=True)
class StepResult:
    """Structured result returned by a backend after executing an instruction."""

    step_index: int
    status: StepStatus
    output: str
    summary: str = ""
    files_touched: tuple[str, ...] = ()
    commands_run: tuple[str, ...] = ()


@dataclass
class OrchestratorState:
    """Mutable state accumulator for the orchestration loop."""

    spec: Spec
    max_steps: int
    current_step: int = 0
    history: list[StepResult] = field(default_factory=list)
    done: bool = False
