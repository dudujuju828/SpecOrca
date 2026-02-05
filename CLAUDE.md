# CLAUDE.md

## Project summary

SpecOrca is a spec-driven, two-role orchestration CLI for software tasks. An **Architect** decomposes work into precise specifications (small, verifiable units of work), and an **Agent** executes each spec using a swappable coding backend (Claude Code by default). The system iterates between planning and execution until every spec is resolved.

## Dev commands

```bash
pip install -e '.[dev]'   # install in editable mode with dev deps
nox                        # run all checks (fmt, lint, typecheck, tests)
nox -s fmt                 # auto-format with ruff
nox -s lint                # lint with ruff
nox -s typecheck           # mypy strict type checking
nox -s tests               # pytest with coverage
```

## Project layout

```
src/spec_orca/           # installable package (CLI, orchestrator, backends, models)
tests/                   # pytest test suite
pyproject.toml           # PEP 621 metadata + tool config (ruff, mypy, pytest, coverage)
noxfile.py               # dev task runner (fmt, lint, typecheck, tests)
```

### Key modules

- `cli.py` — argument parsing and entry point (`spec-orca`)
- `orchestrator.py` — orchestration loop and summaries
- `architect.py` — SimpleArchitect (deterministic YAML planner)
- `agent.py` — Agent role (executes specs via backend)
- `backend.py` — Backend protocol definition
- `backends/mock.py` — deterministic mock backend (default)
- `backends/claude.py` — Claude Code backend (subprocess)
- `models.py` — Spec, Result, Context data models
- `spec.py` — YAML spec loader and validation

## Tooling and conventions

- **Formatting / linting**: ruff (line length 99, target Python 3.11)
- **Type checking**: mypy in strict mode — all public APIs must have type annotations
- **Tests**: pytest with coverage; minimum coverage threshold is 80%
- **Pre-commit**: hooks available via `pre-commit install`

## Python version

Minimum Python version is **3.11**.

## Before committing

Every commit must leave all checks passing. Run `nox` (or the individual sessions) before committing.
