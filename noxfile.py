"""Nox sessions for SpecOrca development."""

from __future__ import annotations

import nox

nox.options.sessions = ["fmt", "lint", "typecheck", "tests"]
nox.options.reuse_existing_virtualenvs = True

PYTHON = "3.11"
SRC = "src/spec_orca"


@nox.session(python=False)
def fmt(session: nox.Session) -> None:
    """Run ruff formatter."""
    session.run("ruff", "format", ".")


@nox.session(python=False)
def lint(session: nox.Session) -> None:
    """Run ruff linter."""
    session.run("ruff", "check", ".", "--fix")


@nox.session(python=False)
def typecheck(session: nox.Session) -> None:
    """Run mypy type checker."""
    session.run("mypy", SRC)


@nox.session(python=False)
def tests(session: nox.Session) -> None:
    """Run pytest with coverage."""
    session.run("pytest", *session.posargs)
