"""Tests for the dev-time auto-commit git helper."""

from __future__ import annotations

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


def _proc(
    args: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
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
# has_changes
# ---------------------------------------------------------------------------


class TestHasChanges:
    def test_clean_repo(self) -> None:
        with mock.patch(
            "subprocess.run",
            return_value=_proc(["git", "status", "--porcelain"], stdout=""),
        ):
            assert has_changes() is False

    def test_tracked_modification(self) -> None:
        with mock.patch(
            "subprocess.run",
            return_value=_proc(["git", "status", "--porcelain"], stdout=" M init.txt\n"),
        ):
            assert has_changes() is True

    def test_untracked_ignored_by_default(self) -> None:
        with mock.patch(
            "subprocess.run",
            return_value=_proc(["git", "status", "--porcelain"], stdout="?? new.txt\n"),
        ):
            assert has_changes(include_untracked=False) is False

    def test_untracked_detected_when_opted_in(self) -> None:
        with mock.patch(
            "subprocess.run",
            return_value=_proc(["git", "status", "--porcelain"], stdout="?? new.txt\n"),
        ):
            assert has_changes(include_untracked=True) is True


# ---------------------------------------------------------------------------
# auto_commit
# ---------------------------------------------------------------------------


class TestAutoCommit:
    def test_no_commit_on_clean_tree(self) -> None:
        responses = [
            _proc(["git", "rev-parse", "--is-inside-work-tree"]),
            _proc(["git", "status", "--porcelain"], stdout=""),
        ]
        with mock.patch("subprocess.run", side_effect=responses) as mocked:
            assert auto_commit("should not commit") is False

        commands = [call.args[0] for call in mocked.call_args_list]
        assert ["git", "add", "-u"] not in commands
        assert ["git", "commit", "-m", "should not commit"] not in commands

    def test_commits_tracked_changes(self) -> None:
        responses = [
            _proc(["git", "rev-parse", "--is-inside-work-tree"]),
            _proc(["git", "status", "--porcelain"], stdout=" M init.txt\n"),
            _proc(["git", "add", "-u"]),
            _proc(
                ["git", "diff", "--cached", "--quiet"],
                returncode=1,
            ),
            _proc(["git", "commit", "-m", "update init file"]),
        ]
        with mock.patch("subprocess.run", side_effect=responses) as mocked:
            result = auto_commit("update init file")

        assert result is True
        commands = [call.args[0] for call in mocked.call_args_list]
        assert ["git", "add", "-u"] in commands
        assert ["git", "add", "-A"] not in commands
        assert ["git", "commit", "-m", "update init file"] in commands

    def test_skips_when_no_staged_changes(self) -> None:
        responses = [
            _proc(["git", "rev-parse", "--is-inside-work-tree"]),
            _proc(["git", "status", "--porcelain"], stdout=" M init.txt\n"),
            _proc(["git", "add", "-u"]),
            _proc(["git", "diff", "--cached", "--quiet"], returncode=0),
        ]
        with mock.patch("subprocess.run", side_effect=responses) as mocked:
            result = auto_commit("should skip")

        assert result is False
        commands = [call.args[0] for call in mocked.call_args_list]
        assert ["git", "commit", "-m", "should skip"] not in commands

    def test_commit_message_is_normalized(self) -> None:
        responses = [
            _proc(["git", "rev-parse", "--is-inside-work-tree"]),
            _proc(["git", "status", "--porcelain"], stdout=" M init.txt\n"),
            _proc(["git", "add", "-u"]),
            _proc(
                ["git", "diff", "--cached", "--quiet"],
                returncode=1,
            ),
            _proc(["git", "commit", "-m", "feat: add widgets"]),
        ]
        with mock.patch("subprocess.run", side_effect=responses) as mocked:
            auto_commit("  add widgets\n\nmore", prefix="feat:")

        commands = [call.args[0] for call in mocked.call_args_list]
        assert ["git", "commit", "-m", "feat: add widgets"] in commands


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
