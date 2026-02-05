"""Tests for the spec_orca.init module and CLI init subcommand."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from spec_orca.cli import main
from spec_orca.init import generate_spec


class TestGenerateSpec:
    def test_creates_valid_yaml_loadable_by_plan(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = tmp_path / "spec.yaml"
        generate_spec("Build a widget", out)

        # The generated file should be loadable by `spec-orca plan`.
        rc = main(["plan", "--spec", str(out)])
        assert rc == 0
        plan_out = capsys.readouterr().out
        assert "spec-1" in plan_out

    def test_includes_goal_string(self, tmp_path: Path) -> None:
        out = tmp_path / "spec.yaml"
        generate_spec("Automate deployments", out)

        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert data["goal"] == "Automate deployments"

    def test_file_exists_error(self, tmp_path: Path) -> None:
        out = tmp_path / "spec.yaml"
        out.write_text("existing", encoding="utf-8")

        with pytest.raises(FileExistsError):
            generate_spec("goal", out)

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "deep" / "spec.yaml"
        result = generate_spec("nested goal", out)

        assert result.exists()
        data = yaml.safe_load(result.read_text(encoding="utf-8"))
        assert data["goal"] == "nested goal"

    def test_returns_resolved_path(self, tmp_path: Path) -> None:
        out = tmp_path / "spec.yaml"
        result = generate_spec("goal", out)

        assert result == out.resolve()
        assert result.is_absolute()


class TestCliInitSubcommand:
    def test_init_creates_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        out = tmp_path / "my-spec.yaml"

        rc = main(["init", "--goal", "Ship feature X", "--output", str(out)])

        assert rc == 0
        assert out.exists()
        stdout = capsys.readouterr().out
        assert "Spec file created" in stdout

    def test_init_existing_file_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        out = tmp_path / "spec.yaml"
        out.write_text("existing content", encoding="utf-8")

        rc = main(["init", "--goal", "duplicate", "--output", str(out)])

        assert rc == 1
        stderr = capsys.readouterr().err
        assert "Error:" in stderr
