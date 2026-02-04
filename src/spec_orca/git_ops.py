"""Git helpers for computing repository deltas."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

__all__ = ["GitStatusDelta", "compute_status_delta", "parse_status_paths"]


@dataclass(frozen=True)
class GitStatusDelta:
    """Diff between two git status snapshots."""

    changed: list[str]


def compute_status_delta(repo_path: Path) -> tuple[GitStatusDelta, str | None]:
    """Compute changed file paths from a git status snapshot.

    Returns a tuple of (delta, warning). If git is unavailable or repo
    is not a git repo, returns an empty delta with a warning message.
    """
    try:
        raw = _run_git(repo_path, ["status", "--porcelain"])
    except (FileNotFoundError, RuntimeError) as exc:
        return GitStatusDelta(changed=[]), str(exc)

    changed = sorted(parse_status_paths(raw))
    return GitStatusDelta(changed=changed), None


def parse_status_paths(raw: str) -> set[str]:
    paths: set[str] = set()
    for line in raw.splitlines():
        if not line:
            continue
        if line.startswith("?? "):
            paths.add(line[3:])
            continue
        status = line[:2]
        payload = line[3:]
        if "->" in payload:
            # rename format: "old -> new"
            parts = [part.strip() for part in payload.split("->", 1)]
            if len(parts) == 2 and parts[1]:
                paths.add(parts[1])
                continue
        if status.strip():
            paths.add(payload)
    return paths


def _run_git(repo_path: Path, args: Iterable[str]) -> str:
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
