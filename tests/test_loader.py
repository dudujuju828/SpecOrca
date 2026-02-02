"""Tests for the specification loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_orca.loader import load_spec
from spec_orca.models import SpecFormat


class TestLoadSpec:
    def test_load_markdown(self, tmp_path: Path) -> None:
        md = tmp_path / "feature.md"
        md.write_text("# Add widgets\nImplement widget support.\n", encoding="utf-8")

        spec = load_spec(md)

        assert spec.title == "Add widgets"
        assert spec.format == SpecFormat.MARKDOWN
        assert spec.source == md.resolve()
        assert "widget support" in spec.raw_content

    def test_load_yaml(self, tmp_path: Path) -> None:
        yml = tmp_path / "feature.yaml"
        yml.write_text("title: Fix bugs\nsteps:\n  - lint\n", encoding="utf-8")

        spec = load_spec(yml)

        assert spec.title == "Fix bugs"
        assert spec.format == SpecFormat.YAML

    def test_load_yml_extension(self, tmp_path: Path) -> None:
        yml = tmp_path / "feature.yml"
        yml.write_text("title: 'Quoted title'\n", encoding="utf-8")

        spec = load_spec(yml)

        assert spec.title == "Quoted title"
        assert spec.format == SpecFormat.YAML

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Spec file not found"):
            load_spec(tmp_path / "nonexistent.md")

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        txt = tmp_path / "spec.txt"
        txt.write_text("hello", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported spec file extension"):
            load_spec(txt)

    def test_title_fallback_to_stem(self, tmp_path: Path) -> None:
        md = tmp_path / "my-feature.md"
        md.write_text("No heading here, just text.\n", encoding="utf-8")

        spec = load_spec(md)

        assert spec.title == "my-feature"
