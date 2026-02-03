"""Specification file parsing and validation.

YAML is the canonical, deterministic format for contributor-authored specs.
Markdown parsing may be added later; for now, Markdown files are rejected with
a clear error.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from spec_orca.models import Spec, SpecFormat

__all__ = ["SpecValidationError", "load_spec_file"]

_YAML_EXTENSIONS = frozenset((".yaml", ".yml"))
_MARKDOWN_EXTENSIONS = frozenset((".md", ".markdown"))
_TOP_LEVEL_KEYS = frozenset(("goal", "specs"))
_SPEC_KEYS = frozenset(
    ("id", "title", "description", "acceptance_criteria", "dependencies"),
)
_MISSING: object = object()


@dataclass(frozen=True)
class _SpecRecord:
    """Validated spec payload."""

    spec_id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    dependencies: list[str]


class SpecValidationError(ValueError):
    """Raised when a spec file fails schema validation."""

    def __init__(self, path: Path, errors: Iterable[str]) -> None:
        self.path = path
        self.errors = [error for error in errors if error]
        details = "\n".join(f"- {error}" for error in self.errors)
        message = f"Invalid spec file: {path}"
        if details:
            message = f"{message}\n{details}"
        super().__init__(message)


def load_spec_file(path: Path) -> tuple[str | None, list[Spec]]:
    """Load and validate a YAML spec file."""
    resolved = path.resolve()
    if not resolved.is_file():
        msg = f"Spec file not found: {resolved}"
        raise FileNotFoundError(msg)

    suffix = resolved.suffix.lower()
    if suffix in _MARKDOWN_EXTENSIONS:
        raise SpecValidationError(
            resolved,
            ["Markdown specs are not supported yet. Use a .yaml or .yml file instead."],
        )
    if suffix not in _YAML_EXTENSIONS:
        raise SpecValidationError(
            resolved,
            [f"Unsupported spec file extension '{suffix}'. Use .yaml or .yml."],
        )

    raw = resolved.read_text(encoding="utf-8")
    data = _parse_yaml(raw, resolved)
    goal, records = _validate_spec_payload(data, resolved)

    specs = [
        Spec(
            id=record.spec_id,
            title=record.title,
            description=record.description,
            acceptance_criteria=list(record.acceptance_criteria),
            dependencies=list(record.dependencies),
            source=resolved,
            format=SpecFormat.YAML,
            raw_content=raw,
        )
        for record in records
    ]
    return goal, specs


def _parse_yaml(raw: str, path: Path) -> Any:
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SpecValidationError(path, [f"YAML parse error: {str(exc).strip()}"]) from exc


def _validate_spec_payload(data: Any, path: Path) -> tuple[str | None, list[_SpecRecord]]:
    errors: list[str] = []
    if data is None:
        raise SpecValidationError(
            path,
            ["File is empty. Expected a mapping with keys: goal (optional) and specs."],
        )
    if not isinstance(data, dict):
        raise SpecValidationError(
            path,
            ["Top-level YAML document must be a mapping with keys: goal (optional) and specs."],
        )

    extra_top = sorted(key for key in data if key not in _TOP_LEVEL_KEYS)
    if extra_top:
        errors.append(
            f"Unexpected top-level keys: {', '.join(extra_top)}. Allowed keys: goal, specs."
        )

    goal = _validate_goal(data.get("goal", _MISSING), errors)
    specs_value = data.get("specs", _MISSING)
    specs_list = _validate_specs_list(specs_value, errors)

    records, ids, dependencies_map = _validate_specs_entries(specs_list, errors)
    _validate_unique_ids(ids, errors)
    _validate_dependencies(ids, dependencies_map, errors)

    if errors:
        raise SpecValidationError(path, errors)
    return goal, records


def _validate_goal(value: Any, errors: list[str]) -> str | None:
    if value is _MISSING:
        return None
    if not isinstance(value, str):
        errors.append("goal must be a string")
        return None
    if not value.strip():
        errors.append("goal must be a non-empty string")
        return None
    return value


def _validate_specs_list(value: Any, errors: list[str]) -> list[Any]:
    if value is _MISSING:
        errors.append("Missing required top-level key: specs")
        return []
    if not isinstance(value, list):
        errors.append("specs must be a list of spec objects")
        return []
    if not value:
        errors.append("specs must contain at least one spec")
    return value


def _validate_specs_entries(
    specs_list: list[Any],
    errors: list[str],
) -> tuple[list[_SpecRecord], list[tuple[str, int]], list[tuple[int, list[str]]]]:
    records: list[_SpecRecord] = []
    ids: list[tuple[str, int]] = []
    dependencies_map: list[tuple[int, list[str]]] = []

    for index, entry in enumerate(specs_list):
        location = f"specs[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{location} must be a mapping")
            continue

        extra_keys = sorted(key for key in entry if key not in _SPEC_KEYS)
        if extra_keys:
            errors.append(
                f"{location} has unexpected keys: {', '.join(extra_keys)}. "
                "Allowed keys: id, title, description, acceptance_criteria, dependencies."
            )

        spec_id = _validate_required_str(entry.get("id", _MISSING), f"{location}.id", errors)
        title = _validate_required_str(entry.get("title", _MISSING), f"{location}.title", errors)
        description = _validate_optional_str(
            entry.get("description", _MISSING),
            f"{location}.description",
            errors,
        )
        acceptance = _validate_required_str_list(
            entry.get("acceptance_criteria", _MISSING),
            f"{location}.acceptance_criteria",
            errors,
        )
        dependencies = _validate_optional_str_list(
            entry.get("dependencies", _MISSING),
            f"{location}.dependencies",
            errors,
        )

        if spec_id is not None:
            ids.append((spec_id, index))
        if dependencies is not None:
            dependencies_map.append((index, dependencies))

        if spec_id is None or title is None or acceptance is None or dependencies is None:
            continue

        record = _SpecRecord(
            spec_id=spec_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance,
            dependencies=dependencies,
        )
        records.append(record)

    return records, ids, dependencies_map


def _validate_unique_ids(ids: list[tuple[str, int]], errors: list[str]) -> None:
    seen: dict[str, int] = {}
    for spec_id, index in ids:
        if spec_id in seen:
            errors.append(
                f"specs[{index}].id duplicates '{spec_id}' from specs[{seen[spec_id]}].id"
            )
        else:
            seen[spec_id] = index


def _validate_dependencies(
    ids: list[tuple[str, int]],
    dependencies_map: list[tuple[int, list[str]]],
    errors: list[str],
) -> None:
    known_ids = {spec_id for spec_id, _ in ids}
    for index, dependencies in dependencies_map:
        for dep in dependencies:
            if dep not in known_ids:
                errors.append(f"specs[{index}].dependencies contains unknown id '{dep}'")


def _validate_required_str(value: Any, path: str, errors: list[str]) -> str | None:
    if value is _MISSING:
        errors.append(f"{path} is required")
        return None
    if not isinstance(value, str):
        errors.append(f"{path} must be a string")
        return None
    if not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return None
    return value


def _validate_optional_str(value: Any, path: str, errors: list[str]) -> str:
    if value is _MISSING:
        return ""
    if not isinstance(value, str):
        errors.append(f"{path} must be a string")
        return ""
    return value


def _validate_required_str_list(
    value: Any,
    path: str,
    errors: list[str],
) -> list[str] | None:
    if value is _MISSING:
        errors.append(f"{path} is required")
        return None
    return _validate_str_list(value, path, errors)


def _validate_optional_str_list(
    value: Any,
    path: str,
    errors: list[str],
) -> list[str] | None:
    if value is _MISSING:
        return []
    return _validate_str_list(value, path, errors)


def _validate_str_list(value: Any, path: str, errors: list[str]) -> list[str] | None:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list of strings")
        return None
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{path}[{index}] must be a string")
            continue
        if not item.strip():
            errors.append(f"{path}[{index}] must be a non-empty string")
            continue
        items.append(item)
    return items
