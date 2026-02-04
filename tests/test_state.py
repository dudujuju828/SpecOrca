"""Tests for project state snapshotting."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spec_orca.models import Result, ResultStatus
from spec_orca.state import ProjectState, build_state, load_state, save_state


def _git_available() -> bool:
    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "init")
    return repo


@pytest.mark.skipif(not _git_available(), reason="git not available")
class TestProjectState:
    def test_build_state_clean_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        state = build_state(repo)

        assert state.repo_path == repo.resolve()
        assert len(state.git_head_sha) == 40
        assert state.tracked_files == ["README.md"]
        assert state.status_summary == "clean"
        assert state.diff_summary == "no diffs"
        assert state.last_test_summary is None
        assert state.history == []

    def test_build_state_dirty_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        (repo / "README.md").write_text("hello\nchange\n", encoding="utf-8")
        (repo / "new.txt").write_text("untracked\n", encoding="utf-8")

        state = build_state(repo)

        assert "README.md" in state.status_summary
        assert "README.md" in state.diff_summary
        assert "new.txt" in state.status_summary

    def test_save_and_load_state(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        state = build_state(repo)
        result = Result(
            status=ResultStatus.SUCCESS,
            summary="ok",
            details="done",
            files_changed=["README.md"],
            commands_run=["pytest"],
        )
        state_with_history = ProjectState(
            repo_path=state.repo_path,
            git_head_sha=state.git_head_sha,
            tracked_files=state.tracked_files,
            status_summary=state.status_summary,
            diff_summary=state.diff_summary,
            last_test_summary="tests passed",
            history=[result],
        )

        path = save_state(state_with_history)
        loaded = load_state(path)

        assert loaded.repo_path == state.repo_path
        assert loaded.git_head_sha == state.git_head_sha
        assert loaded.tracked_files == state.tracked_files
        assert loaded.last_test_summary == "tests passed"
        assert len(loaded.history) == 1
        assert loaded.history[0].status == ResultStatus.SUCCESS
        assert loaded.history[0].files_changed == ["README.md"]

    def test_resume_from_state_file(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        base_state = build_state(repo)
        first = Result(
            status=ResultStatus.SUCCESS,
            summary="first",
            details="done",
            files_changed=["README.md"],
            commands_run=["pytest"],
        )
        initial = ProjectState(
            repo_path=base_state.repo_path,
            git_head_sha=base_state.git_head_sha,
            tracked_files=base_state.tracked_files,
            status_summary=base_state.status_summary,
            diff_summary=base_state.diff_summary,
            history=[first],
        )

        path = save_state(initial)
        loaded = load_state(path)
        second = Result(
            status=ResultStatus.SUCCESS,
            summary="second",
            details="done",
            files_changed=["README.md"],
            commands_run=["pytest"],
        )
        resumed = ProjectState(
            repo_path=loaded.repo_path,
            git_head_sha=loaded.git_head_sha,
            tracked_files=loaded.tracked_files,
            status_summary=loaded.status_summary,
            diff_summary=loaded.diff_summary,
            last_test_summary=loaded.last_test_summary,
            history=[*loaded.history, second],
        )

        resumed_path = save_state(resumed, tmp_path / "state-resumed.json")
        reloaded = load_state(resumed_path)

        assert len(reloaded.history) == 2
        assert reloaded.history[0].summary == "first"
        assert reloaded.history[1].summary == "second"
