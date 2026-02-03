"""Tests for YAML spec parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_orca.models import SpecFormat
from spec_orca.spec import SpecValidationError, load_spec_file

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


class TestLoadSpecFile:
    def test_loads_valid_yaml(self) -> None:
        goal, specs = load_spec_file(FIXTURES / "valid.yaml")

        assert goal == "Ship v1"
        assert len(specs) == 2

        first = specs[0]
        assert first.id == "core-models"
        assert first.title == "Add core models"
        assert first.description == "Define Spec/Result dataclasses."
        assert first.acceptance_criteria == [
            "Spec dataclass exists",
            "Result dataclass exists",
        ]
        assert first.dependencies == []
        assert first.format == SpecFormat.YAML
        assert first.source == (FIXTURES / "valid.yaml").resolve()

        second = specs[1]
        assert second.id == "yaml-loader"
        assert second.dependencies == ["core-models"]

    def test_missing_specs_key_raises(self) -> None:
        with pytest.raises(SpecValidationError) as excinfo:
            load_spec_file(FIXTURES / "invalid_missing_specs.yaml")

        message = str(excinfo.value)
        assert "Missing required top-level key: specs" in message
        assert "Invalid spec file" in message

    def test_invalid_fields_reported(self) -> None:
        with pytest.raises(SpecValidationError) as excinfo:
            load_spec_file(FIXTURES / "invalid_bad_fields.yaml")

        message = str(excinfo.value)
        assert "specs[0].id must be a string" in message
        assert "specs[0].title must be a non-empty string" in message
        assert "specs[0].acceptance_criteria must be a list of strings" in message
        assert "specs[0].dependencies[0] must be a string" in message
        assert "unexpected keys" in message.lower()
