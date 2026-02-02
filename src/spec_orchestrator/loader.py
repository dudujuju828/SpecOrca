"""Specification loader -- reads Markdown or YAML files into Spec objects."""

from __future__ import annotations

from pathlib import Path

from spec_orchestrator.models import Spec, SpecFormat

_MARKDOWN_EXTENSIONS = frozenset((".md", ".markdown"))
_YAML_EXTENSIONS = frozenset((".yml", ".yaml"))


def _detect_format(path: Path) -> SpecFormat:
    """Detect spec format from file extension."""
    suffix = path.suffix.lower()
    if suffix in _MARKDOWN_EXTENSIONS:
        return SpecFormat.MARKDOWN
    if suffix in _YAML_EXTENSIONS:
        return SpecFormat.YAML
    msg = f"Unsupported spec file extension: {suffix}"
    raise ValueError(msg)


def _extract_title(content: str, fmt: SpecFormat, fallback: str) -> str:
    """Extract a title from the spec content, falling back to *fallback*."""
    if fmt == SpecFormat.MARKDOWN:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.removeprefix("# ").strip()

    if fmt == SpecFormat.YAML:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("title:"):
                return stripped.split(":", 1)[1].strip().strip("\"'")

    return fallback


def load_spec(path: Path) -> Spec:
    """Load a specification from a file path.

    Args:
        path: Path to a Markdown or YAML specification file.

    Returns:
        A Spec object with the loaded content.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the file extension is unsupported.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        msg = f"Spec file not found: {resolved}"
        raise FileNotFoundError(msg)

    content = resolved.read_text(encoding="utf-8")
    fmt = _detect_format(resolved)
    title = _extract_title(content, fmt, fallback=resolved.stem)
    return Spec(source=resolved, format=fmt, title=title, raw_content=content)
