"""Spec scaffold / template generation.

Provides a helper to bootstrap a new spec YAML file with a placeholder entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

__all__ = ["generate_spec"]


def generate_spec(goal: str, output: Path) -> Path:
    """Generate a starter spec YAML file.

    Parameters
    ----------
    goal:
        High-level goal description for the spec file.
    output:
        Path where the YAML file will be written.

    Returns
    -------
    Path
        The resolved output path.

    Raises
    ------
    FileExistsError
        If *output* already exists.
    """
    resolved = output.resolve()
    if resolved.exists():
        msg = f"File already exists: {resolved}"
        raise FileExistsError(msg)

    data: dict[str, Any] = {
        "goal": goal,
        "specs": [
            {
                "id": "spec-1",
                "title": "TODO: describe first task",
                "description": "",
                "acceptance_criteria": ["TODO: add criterion"],
                "dependencies": [],
            },
        ],
    }

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return resolved
