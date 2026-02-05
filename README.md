<p align="center">
  <img src="assets/specorca.png" alt="SpecOrca logo" width="200">
</p>

# SpecOrca

[![CI](https://github.com/anthropics/spec-orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/anthropics/spec-orchestrator/actions/workflows/ci.yml)

A spec-driven, two-role orchestration CLI for software tasks.
An **Architect** decomposes work into precise specifications; an **Agent**
executes each spec using a swappable coding backend (Claude Code by default).

| | |
|---|---|
| **Package** | `spec_orca` |
| **CLI** | `spec-orca` |
| **Python** | >= 3.11 |
| **License** | [MIT](LICENSE) |

## What it does

SpecOrca runs an iterative loop:

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
pip install spec-orca
```

## Quickstart

```bash
# Verify the install
spec-orca --version

# Show available commands
spec-orca --help

# Create a minimal spec
spec-orca init --goal "Ship a greeting"

# Validate and print ordered specs
spec-orca plan --spec spec.yaml

# Run with the mock backend (no AI, deterministic)
spec-orca run --spec spec.yaml --backend mock --max-steps 1

# Run with Claude Code (requires claude CLI on PATH)
spec-orca run --spec spec.yaml --backend claude --max-steps 1 --allow-all

# Check environment health
spec-orca doctor --spec spec.yaml --backend claude
```

## CLI reference

```
$ spec-orca --help
usage: spec-orca [-h] [--version] {run,plan,doctor,init} ...

SpecOrca — a spec-driven two-role orchestrator (Architect / Agent).

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit

commands:
  run          Run the orchestration loop.
  plan         Validate and print the spec plan.
  doctor       Check environment health.
  init         Scaffold a new spec YAML file.
```

## Spec format

Spec files are YAML documents with the following schema:

| Field | Type | Description |
|---|---|---|
| `goal` | string | High-level objective for the run. |
| `specs` | list | Ordered list of spec objects. |

Each spec object contains:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier for the spec. |
| `title` | string | yes | Short human-readable title. |
| `description` | string | no | Longer explanation of the work. |
| `acceptance_criteria` | list[string] | yes | Conditions that must be met. |
| `dependencies` | list[string] | no | IDs of specs that must complete first. |

Example:

```yaml
goal: "Ship a greeting"
specs:
  - id: "greet"
    title: "Print hello"
    description: "Create a script that prints a greeting."
    acceptance_criteria:
      - "Program prints 'hello'."
    dependencies: []
```

## Backend notes

The default backend is `mock` for deterministic execution. To use Claude Code,
run with `--backend claude` and ensure the `claude` executable is available.
To use a different backend, implement the `Backend` protocol defined in the
package and pass it to the orchestrator at construction time.
Backend documentation will expand as the interface stabilises.

## Claude Code backend

Prerequisites:
- Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code).
- Ensure the CLI is on `PATH` and responding to `claude -v`.

Verify the environment:
```bash
claude -v
spec-orca doctor --backend claude --spec spec.yaml
```

Minimal run:
```bash
spec-orca run --backend claude --spec spec.yaml --max-steps 1 --allow-all
```

Tool permissions:

Claude Code runs in non-interactive (`-p`) mode, which denies all tool use
by default. You **must** grant permissions or the agent will not be able to
read, write, or execute anything.

The quickest way to get started is `--allow-all`, which grants access to
every standard Claude Code tool (Bash, Read, Write, Edit, Glob, Grep,
WebFetch, WebSearch, NotebookEdit):

```bash
spec-orca run --backend claude --spec spec.yaml --max-steps 3 --allow-all
```

For tighter control, pass an explicit allowlist instead:

```bash
spec-orca run --backend claude --spec spec.yaml \
  --claude-allowed-tools "Read(*)" \
  --claude-allowed-tools "Write(*)" \
  --claude-allowed-tools "Edit(*)" \
  --claude-disallowed-tools "Bash(*)"
```

You can also block specific tools with `--claude-disallowed-tools` or
restrict to an exact set with `--claude-tools`.

Claude configuration precedence (highest to lowest):
1) CLI flags
2) Config file (`spec-orca.toml` or `[tool.spec_orca]` in `pyproject.toml`)
3) Environment variables (`CLAUDE_CODE_*`)
4) Defaults

Config example:
```toml
[tool.spec_orca]
claude_bin = "claude"
claude_allowed_tools = ["read:*", "write:*"]
claude_disallowed_tools = ["rm:*"]
claude_tools = ["edit", "read"]
claude_max_turns = 4
claude_max_budget_usd = 2.5
claude_timeout_seconds = 300
claude_no_session_persistence = true
```

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

When iterating on this repository you can let SpecOrca commit
changes automatically after each successful run:

```bash
# Commit with an auto-generated message
spec-orca run --spec spec.yaml --auto-commit

# Add a Conventional Commit prefix
spec-orca run --spec spec.yaml --auto-commit --commit-prefix feat

# Multi-step run with auto-commit
spec-orca run --spec spec.yaml --max-steps 3 --auto-commit --commit-prefix chore
```

Behaviour:
- **Off by default** - auto-commit only runs when `--auto-commit` is passed.
- Only **tracked files** are staged (`git add -u`).
- **No commit on a clean tree** - if nothing changed, the commit is skipped.
- **No commit on failed runs** - runs that exit non-zero never auto-commit.
- Commit messages are single-line, normalized, and include the prefix when
  provided (e.g. `feat: spec-orca run: Add widgets`).
- The git helper lives in `spec_orca/dev/git.py` and does not affect
  the core orchestration logic.

## Project layout

```
src/spec_orca/           # installable package
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
