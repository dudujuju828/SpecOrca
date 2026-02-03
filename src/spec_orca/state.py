"""Project state snapshotting utilities."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from spec_orca.models import Result, ResultStatus

__all__ = ["ProjectState", "build_state", "load_state", "save_state"]

_STATE_FILENAME = "state.json"


@dataclass(frozen=True)
class ProjectState:
    """Immutable snapshot of repository state for orchestration."""

    repo_path: Path
    git_head_sha: str
    tracked_files: list[str]
    status_summary: str
    diff_summary: str
    last_test_summary: str | None = None
    history: list[Result] = field(default_factory=list)


def build_state(repo_path: Path) -> ProjectState:
    """Build a deterministic snapshot of the repository state."""
    resolved = repo_path.resolve()
    if not resolved.exists():
        msg = f"Repository path not found: {resolved}"
        raise FileNotFoundError(msg)

    git_head_sha = _run_git(resolved, ["rev-parse", "HEAD"]).strip()
    tracked_files = sorted(_run_git(resolved, ["ls-files"]).splitlines())
    status_summary = _summarize_status(_run_git(resolved, ["status", "--porcelain"]))
    diff_summary = _summarize_diff(_run_git(resolved, ["diff", "--stat"]))

    return ProjectState(
        repo_path=resolved,
        git_head_sha=git_head_sha,
        tracked_files=tracked_files,
        status_summary=status_summary,
        diff_summary=diff_summary,
    )


def save_state(state: ProjectState, path: Path | None = None) -> Path:
    """Persist a ProjectState snapshot to JSON."""
    target = path or (state.repo_path / _STATE_FILENAME)
    payload = _state_to_dict(state)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_state(path: Path) -> ProjectState:
    """Load a ProjectState snapshot from JSON."""
    resolved = path.resolve()
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Invalid state file (expected JSON object): {resolved}"
        raise ValueError(msg)
    return _state_from_dict(data)


def _run_git(repo_path: Path, args: list[str]) -> str:
    cmd = ["git", *args]
    proc = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or f"Git command failed: {' '.join(cmd)}"
        raise RuntimeError(msg)
    return proc.stdout


def _summarize_status(raw: str) -> str:
    lines = raw.splitlines()
    if not lines:
        return "clean"
    return "\n".join(lines)


def _summarize_diff(raw: str) -> str:
    lines = raw.splitlines()
    if not lines:
        return "no diffs"
    return "\n".join(lines)


def _state_to_dict(state: ProjectState) -> dict[str, Any]:
    payload = asdict(state)
    payload["repo_path"] = str(state.repo_path)
    payload["history"] = [_result_to_dict(result) for result in state.history]
    return payload


def _state_from_dict(data: dict[str, Any]) -> ProjectState:
    repo_path = Path(_require_str(data, "repo_path"))
    git_head_sha = _require_str(data, "git_head_sha")
    tracked_files = _require_list(data, "tracked_files")
    status_summary = _require_str(data, "status_summary")
    diff_summary = _require_str(data, "diff_summary")
    last_test_summary = data.get("last_test_summary")
    if last_test_summary is not None and not isinstance(last_test_summary, str):
        msg = "last_test_summary must be a string or null"
        raise ValueError(msg)
    history_raw = data.get("history", [])
    if not isinstance(history_raw, list):
        msg = "history must be a list"
        raise ValueError(msg)
    history = [_result_from_dict(item) for item in history_raw]
    return ProjectState(
        repo_path=repo_path,
        git_head_sha=git_head_sha,
        tracked_files=tracked_files,
        status_summary=status_summary,
        diff_summary=diff_summary,
        last_test_summary=last_test_summary,
        history=history,
    )


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        msg = f"{key} must be a string"
        raise ValueError(msg)
    return value


def _require_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = f"{key} must be a list of strings"
        raise ValueError(msg)
    return value


def _result_to_dict(result: Result) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "summary": result.summary,
        "details": result.details,
        "files_changed": list(result.files_changed),
        "commands_run": list(result.commands_run),
        "error": result.error,
    }


def _result_from_dict(data: Any) -> Result:
    if not isinstance(data, dict):
        msg = "result entry must be a mapping"
        raise ValueError(msg)
    status_raw = data.get("status")
    if not isinstance(status_raw, str):
        msg = "result.status must be a string"
        raise ValueError(msg)
    status = ResultStatus(status_raw)
    summary = data.get("summary")
    if not isinstance(summary, str):
        msg = "result.summary must be a string"
        raise ValueError(msg)
    details = data.get("details", "")
    if not isinstance(details, str):
        msg = "result.details must be a string"
        raise ValueError(msg)
    files_changed = data.get("files_changed", [])
    commands_run = data.get("commands_run", [])
    if not isinstance(files_changed, list) or not all(
        isinstance(item, str) for item in files_changed
    ):
        msg = "result.files_changed must be a list of strings"
        raise ValueError(msg)
    if not isinstance(commands_run, list) or not all(
        isinstance(item, str) for item in commands_run
    ):
        msg = "result.commands_run must be a list of strings"
        raise ValueError(msg)
    error = data.get("error")
    if error is not None and not isinstance(error, str):
        msg = "result.error must be a string or null"
        raise ValueError(msg)
    return Result(
        status=status,
        summary=summary,
        details=details,
        files_changed=files_changed,
        commands_run=commands_run,
        error=error,
    )
