"""Tests for the dev-time auto-commit git helper."""

from __future__ import annotations

import logging
import subprocess
from unittest import mock

import pytest

from spec_orca.dev.git import (
    GitError,
    _run_git,
    auto_commit,
    has_changes,
    normalize_message,
)

# ---------------------------------------------------------------------------
# normalize_message
# ---------------------------------------------------------------------------


class TestNormalizeMessage:
    def test_plain_message(self) -> None:
        assert normalize_message("add widgets") == "add widgets"

    def test_strips_whitespace(self) -> None:
        assert normalize_message("  fix bug  ") == "fix bug"

    def test_takes_first_line(self) -> None:
        assert normalize_message("first\nsecond\nthird") == "first"

    def test_skips_empty_lines(self) -> None:
        assert normalize_message("\n\n  real line  \n") == "real line"

    def test_fallback_on_empty(self) -> None:
        assert normalize_message("") == "auto-commit"
        assert normalize_message("   \n\n  ") == "auto-commit"

    def test_with_prefix(self) -> None:
        assert normalize_message("add tests", prefix="test") == "test: add tests"

    def test_prefix_strips_trailing_colon(self) -> None:
        assert normalize_message("add tests", prefix="test:") == "test: add tests"

    def test_prefix_strips_whitespace(self) -> None:
        assert normalize_message("add tests", prefix="  feat  ") == "feat: add tests"

    def test_prefix_none_no_tag(self) -> None:
        result = normalize_message("something", prefix=None)
        assert result == "something"
        assert ":" not in result[:5]

    def test_prefix_with_empty_message_uses_fallback(self) -> None:
        result = normalize_message("", prefix="chore")
        assert result == "chore: auto-commit"


# ---------------------------------------------------------------------------
# Integration tests using a real temporary git repo
# ---------------------------------------------------------------------------


@pytest.fixture()
def git_repo(tmp_path: pytest.TempPathFactory) -> pytest.TempPathFactory:
    """Create a temporary git repo with an initial commit."""
    subprocess.run(
        ["git", "init"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    # Create initial commit so HEAD exists.
    init_file = tmp_path / "init.txt"  # type: ignore[operator]
    init_file.write_text("init\n")
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    return tmp_path  # type: ignore[return-value]


def _git_log(repo_path: object) -> list[str]:
    """Return commit subject lines from the repo."""
    result = subprocess.run(
        ["git", "log", "--format=%s"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


# ---------------------------------------------------------------------------
# has_changes
# ---------------------------------------------------------------------------


class TestHasChanges:
    def test_clean_repo(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        assert has_changes() is False

    def test_tracked_modification(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        init_file = git_repo / "init.txt"  # type: ignore[operator]
        init_file.write_text("modified\n")
        assert has_changes() is True

    def test_untracked_ignored_by_default(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        new_file = git_repo / "untracked.txt"  # type: ignore[operator]
        new_file.write_text("new\n")
        assert has_changes(include_untracked=False) is False

    def test_untracked_detected_when_opted_in(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        new_file = git_repo / "untracked.txt"  # type: ignore[operator]
        new_file.write_text("new\n")
        assert has_changes(include_untracked=True) is True

    def test_staged_change_detected(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        init_file = git_repo / "init.txt"  # type: ignore[operator]
        init_file.write_text("staged\n")
        subprocess.run(
            ["git", "add", "init.txt"],
            cwd=str(git_repo),
            capture_output=True,
            check=True,
        )
        assert has_changes() is True

    def test_deleted_file_detected(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        init_file = git_repo / "init.txt"  # type: ignore[operator]
        init_file.unlink()
        assert has_changes() is True


# ---------------------------------------------------------------------------
# auto_commit
# ---------------------------------------------------------------------------


class TestAutoCommit:
    def test_no_commit_on_clean_tree(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        assert auto_commit("should not commit") is False
        assert len(_git_log(git_repo)) == 1  # only initial commit

    def test_commits_tracked_changes(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        init_file = git_repo / "init.txt"  # type: ignore[operator]
        init_file.write_text("changed\n")

        result = auto_commit("update init file")

        assert result is True
        log = _git_log(git_repo)
        assert log[0] == "update init file"

    def test_prefix_applied(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        init_file = git_repo / "init.txt"  # type: ignore[operator]
        init_file.write_text("v2\n")

        auto_commit("update file", prefix="chore")

        log = _git_log(git_repo)
        assert log[0] == "chore: update file"

    def test_untracked_not_staged_by_default(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        new_file = git_repo / "brand_new.txt"  # type: ignore[operator]
        new_file.write_text("new content\n")

        result = auto_commit("should skip")

        assert result is False
        assert len(_git_log(git_repo)) == 1

    def test_untracked_staged_when_opted_in(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        new_file = git_repo / "brand_new.txt"  # type: ignore[operator]
        new_file.write_text("new content\n")

        result = auto_commit("add new file", stage_untracked=True)

        assert result is True
        log = _git_log(git_repo)
        assert log[0] == "add new file"

    def test_raises_outside_git_repo(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(tmp_path))
        with pytest.raises(GitError):
            auto_commit("should fail")

    def test_logs_clean_tree_skip(
        self,
        git_repo: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        with caplog.at_level(logging.INFO, logger="spec_orca.dev.git"):
            auto_commit("nothing to do")
        assert "clean" in caplog.text.lower()

    def test_multiple_commits_accumulate(
        self, git_repo: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(str(git_repo))
        init_file = git_repo / "init.txt"  # type: ignore[operator]

        init_file.write_text("v2\n")
        auto_commit("first change", prefix="feat")

        init_file.write_text("v3\n")
        auto_commit("second change", prefix="fix")

        log = _git_log(git_repo)
        assert log[0] == "fix: second change"
        assert log[1] == "feat: first change"
        assert len(log) == 3  # initial + 2 auto-commits


# ---------------------------------------------------------------------------
# _run_git error paths
# ---------------------------------------------------------------------------


class TestRunGitErrors:
    def test_git_not_found_raises(self) -> None:
        """FileNotFoundError from subprocess should raise GitError."""
        with (
            mock.patch("subprocess.run", side_effect=FileNotFoundError("not found")),
            pytest.raises(GitError, match="git executable not found"),
        ):
            _run_git("status")

    def test_git_command_failure_raises(self) -> None:
        """CalledProcessError should raise GitError with stderr."""
        exc = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "log"], stderr="fatal: bad"
        )
        with (
            mock.patch("subprocess.run", side_effect=exc),
            pytest.raises(GitError, match="fatal: bad"),
        ):
            _run_git("log")

    def test_check_false_does_not_raise(self) -> None:
        """_run_git with check=False should not raise on non-zero exit."""
        fake_proc = subprocess.CompletedProcess(
            args=["git", "diff", "--cached", "--quiet"],
            returncode=1,
            stdout="",
            stderr="",
        )
        with mock.patch("subprocess.run", return_value=fake_proc):
            result = _run_git("diff", "--cached", "--quiet", check=False)
        assert result.returncode == 1
