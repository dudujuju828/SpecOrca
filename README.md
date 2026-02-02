# spec-orchestrator

A spec-driven two-role orchestrator (Architect / Agent) with swappable coding backends.

## Installation

```bash
pip install -e .
```

## Usage

```bash
spec-orchestrator --help
spec-orchestrator --version
```

## Development

Install with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run all checks (format, lint, typecheck, tests) via **nox**:

```bash
nox                    # run all default sessions
nox -s lint            # lint only
nox -s typecheck       # mypy only
nox -s tests           # pytest + coverage only
nox -s fmt             # format only
```

Install pre-commit hooks:

```bash
pre-commit install
```
