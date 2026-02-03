"""Deterministic architect implementation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from spec_orca.models import Result, ResultStatus, Spec, SpecStatus
from spec_orca.spec import load_spec_file

__all__ = ["SimpleArchitect"]


class SimpleArchitect:
    """Deterministic architect that orders specs by dependencies."""

    def __init__(self, spec_path: Path, *, max_attempts: int = 1) -> None:
        goal, specs = load_spec_file(spec_path)
        self.goal = goal
        self._specs = _order_specs(specs)
        self._index = {spec.id: idx for idx, spec in enumerate(self._specs)}
        self._max_attempts = max_attempts

    @property
    def specs(self) -> list[Spec]:
        return list(self._specs)

    def runnable_specs(self) -> list[Spec]:
        runnable: list[Spec] = []
        for spec in self._specs:
            if not _can_attempt(spec, self._max_attempts):
                continue
            if not _dependencies_satisfied(spec, self._index, self._specs):
                continue
            runnable.append(spec)
        return runnable

    def mark_in_progress(self, spec_id: str) -> Spec:
        spec = self._get_spec(spec_id)
        if not _can_attempt(spec, self._max_attempts):
            msg = f"Spec '{spec_id}' is not eligible to run"
            raise ValueError(msg)
        if not _dependencies_satisfied(spec, self._index, self._specs):
            msg = f"Dependencies not satisfied for spec '{spec_id}'"
            raise ValueError(msg)
        updated = replace(spec, status=SpecStatus.IN_PROGRESS)
        self._replace_spec(updated)
        return updated

    def record_result(self, spec_id: str, result: Result) -> Spec:
        spec = self._get_spec(spec_id)
        status = _status_from_result(result)
        updated = replace(spec, status=status, attempts=spec.attempts + 1)
        self._replace_spec(updated)
        return updated

    def _get_spec(self, spec_id: str) -> Spec:
        if spec_id not in self._index:
            msg = f"Unknown spec id: {spec_id}"
            raise KeyError(msg)
        return self._specs[self._index[spec_id]]

    def _replace_spec(self, updated: Spec) -> None:
        self._specs[self._index[updated.id]] = updated


def _order_specs(specs: list[Spec]) -> list[Spec]:
    if not specs:
        return []
    index_by_id = {spec.id: idx for idx, spec in enumerate(specs)}
    graph: dict[str, list[str]] = {spec.id: [] for spec in specs}
    indegree: dict[str, int] = {spec.id: 0 for spec in specs}
    for spec in specs:
        for dep in spec.dependencies:
            graph.setdefault(dep, []).append(spec.id)
            indegree[spec.id] = indegree.get(spec.id, 0) + 1

    import heapq

    heap: list[tuple[int, str]] = []
    for spec in specs:
        if indegree.get(spec.id, 0) == 0:
            heapq.heappush(heap, (index_by_id[spec.id], spec.id))

    ordered_ids: list[str] = []
    while heap:
        _, spec_id = heapq.heappop(heap)
        ordered_ids.append(spec_id)
        for child in graph.get(spec_id, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(heap, (index_by_id.get(child, 0), child))

    if len(ordered_ids) != len(specs):
        msg = "Circular dependencies detected in spec graph"
        raise ValueError(msg)

    id_to_spec = {spec.id: spec for spec in specs}
    return [id_to_spec[spec_id] for spec_id in ordered_ids]


def _dependencies_satisfied(
    spec: Spec,
    index: dict[str, int],
    specs: list[Spec],
) -> bool:
    for dep in spec.dependencies:
        dep_index = index.get(dep)
        if dep_index is None:
            return False
        dep_spec = specs[dep_index]
        if dep_spec.status != SpecStatus.DONE:
            return False
    return True


def _can_attempt(spec: Spec, max_attempts: int) -> bool:
    if spec.status == SpecStatus.DONE:
        return False
    if spec.status == SpecStatus.IN_PROGRESS:
        return False
    if spec.status == SpecStatus.PENDING:
        return True
    if spec.status == SpecStatus.FAILED:
        return spec.attempts < max_attempts
    return False


def _status_from_result(result: Result) -> SpecStatus:
    if result.status == ResultStatus.SUCCESS:
        return SpecStatus.DONE
    return SpecStatus.FAILED
