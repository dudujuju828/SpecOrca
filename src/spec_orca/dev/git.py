"""Git helpers for dev-time auto-commit support.

This module is **isolated** from the core orchestration logic.  It is only
invoked when the user explicitly opts in via ``--auto-commit``.

Safety guarantees:
- No commit is created when the working tree is clean.
- Only tracked files are staged (``git add -u``).
- Commits are skipped if staging produces no changes.
- All git interactions use ``subprocess.run`` with ``shell=False``.
"""

from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger(__name__)

_GIT = "git"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def auto_commit(
    message: str,
    *,
    prefix: str | None = None,
) -> bool:
    """Stage changes and commit if the tree is dirty.

    Args:
        message: The commit message body (will be normalized).
        prefix: Optional Conventional Commit prefix (e.g. ``"feat"``).
            Prepended as ``"prefix: message"``.

    Returns:
        True if a commit was created, False if skipped (clean tree).

    Raises:
        GitError: If a git command fails unexpectedly.
    """
    _ensure_git()

    if not has_changes():
        log.info("Working tree is clean - skipping auto-commit.")
        return False

    _stage_tracked()

    if not _has_staged_changes():
        log.info("Nothing staged after git-add - skipping auto-commit.")
        return False

    full_message = normalize_message(message, prefix=prefix)
    _commit(full_message)
    log.info("Auto-committed: %s", full_message)
    return True


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------


def normalize_message(message: str, *, prefix: str | None = None) -> str:
    """Build a single-line, normalized commit message.

    - Strips leading/trailing whitespace.
    - Collapses to one line (takes the first non-empty line).
    - Prepends the *prefix* in ``prefix: ...`` form if given.
    """
    first_line = ""
    for line in message.splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break
    if not first_line:
        first_line = "auto-commit"

    if prefix:
        tag = prefix.strip().rstrip(":")
        return f"{tag}: {first_line}"
    return first_line


# ---------------------------------------------------------------------------
# Git queries
# ---------------------------------------------------------------------------


def has_changes(*, include_untracked: bool = False) -> bool:
    """Return True if the working tree has uncommitted changes."""
    # Check tracked modifications (staged + unstaged).
    result = _run_git("status", "--porcelain")
    for line in result.stdout.splitlines():
        indicator = line[:2] if len(line) >= 2 else ""
        # '??' means untracked.
        if indicator == "??" and not include_untracked:
            continue
        if line.strip():
            return True
    return False


# ---------------------------------------------------------------------------
# Git mutations
# ---------------------------------------------------------------------------


def _stage_tracked() -> None:
    _run_git("add", "-u")


def _has_staged_changes() -> bool:
    result = _run_git("diff", "--cached", "--quiet", check=False)
    return result.returncode != 0


def _commit(message: str) -> None:
    _run_git("commit", "-m", message)


def _ensure_git() -> None:
    try:
        _run_git("rev-parse", "--is-inside-work-tree")
    except GitError as exc:
        msg = "Not inside a git repository. Auto-commit requires a git repo."
        raise GitError(msg) from exc


# ---------------------------------------------------------------------------
# Low-level runner
# ---------------------------------------------------------------------------


class GitError(RuntimeError):
    """Raised when a git subprocess fails."""


def _run_git(
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = [_GIT, *args]
    log.debug("Running: %s", " ".join(cmd))
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
    except subprocess.CalledProcessError as exc:
        msg = f"git {args[0]} failed (exit {exc.returncode}): {exc.stderr.strip()}"
        log.error(msg)
        raise GitError(msg) from exc
    except FileNotFoundError as exc:
        msg = "git executable not found. Is git installed and on PATH?"
        print(f"Error: {msg}", file=sys.stderr)
        raise GitError(msg) from exc
