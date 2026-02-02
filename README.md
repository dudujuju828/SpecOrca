# spec-orchestrator

A spec-driven, two-role orchestration CLI for software tasks.
An **Architect** decomposes work into precise specifications; an **Agent**
executes each spec using a swappable coding backend (Claude Code by default).

| | |
|---|---|
| **Package** | `spec_orchestrator` |
| **CLI** | `spec-orchestrator` |
| **Python** | >= 3.11 |
| **License** | [MIT](LICENSE) |

## What it does

`spec-orchestrator` runs an iterative loop:

1. The **Architect** reads a project state and produces a prioritised list of
   specifications (small, verifiable units of work).
2. The **Agent** picks the next spec, executes it through a coding backend, and
   reports the result.
3. The loop repeats until every spec is resolved or the Architect decides to
   stop.

The coding backend is an interface — the default implementation shells out to
[Claude Code](https://docs.anthropic.com/en/docs/claude-code), but any backend
that satisfies the `Backend` protocol can be substituted.

## Prerequisites

- Python >= 3.11
- (Optional) [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
  installed and on `PATH` if using the default backend.

## Installation

```bash
# From a local clone (editable / development)
pip install -e ".[dev]"

# Production install (once published)
pip install spec-orchestrator
```

## Quickstart

```bash
# Verify the install
spec-orchestrator --version

# Show available commands
spec-orchestrator --help
```

> **Note:** Subcommands for running the orchestration loop are not yet
> implemented. See the [changelog](CHANGELOG.md) for progress.

## CLI reference

```
$ spec-orchestrator --help
usage: spec-orchestrator [-h] [--version]

A spec-driven two-role orchestrator (Architect / Agent).

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
```

## Backend notes

The default backend shells out to `claude-code` (the Claude Code CLI).
To use a different backend, implement the `Backend` protocol defined in the
package and pass it to the orchestrator at construction time.
Backend documentation will expand as the interface stabilises.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all checks (format, lint, typecheck, tests)
nox

# Run individual sessions
nox -s fmt             # auto-format
nox -s lint            # ruff lint
nox -s typecheck       # mypy strict
nox -s tests           # pytest + coverage

# Install pre-commit hooks
pre-commit install
```

### Auto-commit (opt-in)

When iterating on this repository you can let `spec-orchestrator` commit
changes automatically after each successful run:

```bash
# Commit with an auto-generated message
spec-orchestrator run --spec spec.md --auto-commit

# Add a Conventional Commit prefix
spec-orchestrator run --spec spec.md --auto-commit --commit-prefix feat

# Multi-step run with auto-commit
spec-orchestrator run --spec spec.md --max-steps 3 --auto-commit --commit-prefix chore
```

Behaviour:
- **Off by default** — auto-commit only runs when `--auto-commit` is passed.
- Only **tracked files** are staged (`git add -u`).  Untracked files are
  never committed unless the code is extended to opt in.
- **No commit on a clean tree** — if nothing changed, the commit is skipped.
- Commit messages are single-line, normalized, and include the prefix when
  provided (e.g. `feat: spec-orchestrator run: Add widgets`).
- The git helper lives in `spec_orchestrator/dev/git.py` and does not affect
  the core orchestration logic.

## Project layout

```
src/spec_orchestrator/   # installable package
tests/                   # pytest test suite
noxfile.py               # dev task runner
pyproject.toml           # PEP 621 metadata + tool config
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design and module map
- [CHANGELOG.md](CHANGELOG.md) — release history (Keep a Changelog)
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community standards
- [SECURITY.md](SECURITY.md) — vulnerability reporting
