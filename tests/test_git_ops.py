"""Tests for git status parsing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_orca.git_ops import compute_status_delta, parse_status_paths


def test_parse_status_paths_handles_untracked_and_modified() -> None:
    raw = """ M file.txt
?? new.txt
"""
    assert parse_status_paths(raw) == {"file.txt", "new.txt"}


def test_parse_status_paths_handles_rename() -> None:
    raw = """R  old.txt -> new.txt
"""
    assert parse_status_paths(raw) == {"new.txt"}


def test_parse_status_paths_ignores_empty() -> None:
    assert parse_status_paths("") == set()


def test_compute_status_delta_handles_git_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("not a git repo")

    monkeypatch.setattr("spec_orca.git_ops._run_git", _boom)
    delta, warning = compute_status_delta(Path("."))
    assert delta.changed == []
    assert warning == "not a git repo"
