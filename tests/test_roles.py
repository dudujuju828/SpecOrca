"""Tests for architect/agent/orchestrator loop."""

from __future__ import annotations

from pathlib import Path

from spec_orca.agent import Agent
from spec_orca.architect import SimpleArchitect
from spec_orca.models import Context, Result, ResultStatus, SpecStatus
from spec_orca.orchestrator import Orchestrator


def _write_spec(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "specs.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _make_context(repo_path: Path, spec_path: Path) -> Context:
    return Context(
        repo_path=repo_path,
        spec_path=spec_path,
        goal="test",
        backend_name="mock",
    )


class RecordingBackend:
    def __init__(self, outcomes: dict[str, ResultStatus] | None = None) -> None:
        self.calls: list[str] = []
        self._outcomes = outcomes or {}

    def execute(self, spec, context):  # type: ignore[no-untyped-def]
        self.calls.append(spec.id)
        status = self._outcomes.get(spec.id, ResultStatus.SUCCESS)
        return Result(status=status, summary=f"{spec.id}:{status.value}")


class FlakyBackend:
    def __init__(self, fail_times: int = 1) -> None:
        self.calls: list[str] = []
        self._fail_times = fail_times
        self._counts: dict[str, int] = {}

    def execute(self, spec, context):  # type: ignore[no-untyped-def]
        self.calls.append(spec.id)
        count = self._counts.get(spec.id, 0) + 1
        self._counts[spec.id] = count
        status = ResultStatus.FAILURE if count <= self._fail_times else ResultStatus.SUCCESS
        return Result(status=status, summary=f"{spec.id}:{status.value}")


class TestDependencyOrdering:
    def test_dependency_ordering_enforced(self, tmp_path: Path) -> None:
        spec_path = _write_spec(
            tmp_path,
            """goal: "test"
specs:
  - id: "a"
    title: "A"
    acceptance_criteria: ["done"]
  - id: "b"
    title: "B"
    acceptance_criteria: ["done"]
    dependencies: ["a"]
  - id: "c"
    title: "C"
    acceptance_criteria: ["done"]
    dependencies: ["b"]
""",
        )
        backend = RecordingBackend()
        architect = SimpleArchitect(spec_path)
        agent = Agent(backend)
        orchestrator = Orchestrator(architect, agent, _make_context(tmp_path, spec_path))

        summary = orchestrator.run(max_steps=5)

        assert backend.calls == ["a", "b", "c"]
        assert summary.completed == 3

    def test_unmet_dependency_not_executed(self, tmp_path: Path) -> None:
        spec_path = _write_spec(
            tmp_path,
            """goal: "test"
specs:
  - id: "a"
    title: "A"
    acceptance_criteria: ["done"]
  - id: "b"
    title: "B"
    acceptance_criteria: ["done"]
    dependencies: ["a"]
""",
        )
        backend = RecordingBackend(outcomes={"a": ResultStatus.FAILURE})
        architect = SimpleArchitect(spec_path)
        agent = Agent(backend)
        orchestrator = Orchestrator(architect, agent, _make_context(tmp_path, spec_path))

        summary = orchestrator.run(max_steps=5, stop_on_failure=False)

        assert backend.calls == ["a"]
        assert summary.failed == 1
        pending = [spec for spec in summary.specs if spec.status == SpecStatus.PENDING]
        assert pending and pending[0].id == "b"


class TestStopConditions:
    def test_stop_on_failure(self, tmp_path: Path) -> None:
        spec_path = _write_spec(
            tmp_path,
            """goal: "test"
specs:
  - id: "a"
    title: "A"
    acceptance_criteria: ["done"]
  - id: "b"
    title: "B"
    acceptance_criteria: ["done"]
""",
        )
        backend = RecordingBackend(outcomes={"a": ResultStatus.FAILURE})
        architect = SimpleArchitect(spec_path)
        agent = Agent(backend)
        orchestrator = Orchestrator(architect, agent, _make_context(tmp_path, spec_path))

        summary = orchestrator.run(max_steps=5, stop_on_failure=True)

        assert backend.calls == ["a"]
        assert summary.failed == 1

    def test_continue_on_failure(self, tmp_path: Path) -> None:
        spec_path = _write_spec(
            tmp_path,
            """goal: "test"
specs:
  - id: "a"
    title: "A"
    acceptance_criteria: ["done"]
  - id: "b"
    title: "B"
    acceptance_criteria: ["done"]
""",
        )
        backend = RecordingBackend(outcomes={"a": ResultStatus.FAILURE})
        architect = SimpleArchitect(spec_path)
        agent = Agent(backend)
        orchestrator = Orchestrator(architect, agent, _make_context(tmp_path, spec_path))

        summary = orchestrator.run(max_steps=5, stop_on_failure=False)

        assert backend.calls == ["a", "b"]
        assert summary.failed == 1
        assert summary.completed == 1


class TestRetryBehavior:
    def test_retry_failed_spec(self, tmp_path: Path) -> None:
        spec_path = _write_spec(
            tmp_path,
            """goal: "test"
specs:
  - id: "a"
    title: "A"
    acceptance_criteria: ["done"]
""",
        )
        backend = FlakyBackend(fail_times=1)
        architect = SimpleArchitect(spec_path, max_attempts=2)
        agent = Agent(backend)
        orchestrator = Orchestrator(architect, agent, _make_context(tmp_path, spec_path))

        summary = orchestrator.run(max_steps=2, stop_on_failure=False)

        assert backend.calls == ["a", "a"]
        spec = summary.specs[0]
        assert spec.attempts == 2
        assert spec.status == SpecStatus.DONE
