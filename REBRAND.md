# Rebrand Plan: spec-orchestrator → SpecOrca

This document defines the target naming conventions and provides a complete
checklist of all name surfaces that must be updated during the rebrand.

## Target State

| Surface              | Current Value            | Target Value       |
|----------------------|--------------------------|--------------------|
| **Display Name**     | spec-orchestrator        | SpecOrca           |
| **CLI Command**      | `spec-orchestrator`      | `spec-orca`        |
| **Python Package**   | `spec_orchestrator`      | `spec_orca`        |
| **Env Var Prefix**   | `SPEC_ORCHESTRATOR_`     | `SPEC_ORCA_`       |

## Naming Conventions

- **Display Name**: `SpecOrca` — used in titles, prose, and marketing
- **CLI Command**: `spec-orca` — kebab-case for shell invocation
- **Python Package**: `spec_orca` — snake_case per PEP 8
- **Environment Variables**: `SPEC_ORCA_*` — uppercase with underscores

## Checklist

### Phase 1: Package Directory (requires `git mv`)

- [ ] `src/spec_orchestrator/` → `src/spec_orca/`

### Phase 2: pyproject.toml

- [ ] `name = "spec-orchestrator"` → `name = "spec-orca"`
- [ ] `authors` attribution text
- [ ] `[project.scripts]` entry point: `spec-orchestrator` → `spec-orca`
- [ ] `[tool.ruff.lint.isort]` known-first-party
- [ ] `[tool.mypy]` packages
- [ ] `[tool.pytest.ini_options]` --cov target
- [ ] `[tool.coverage.run]` source

### Phase 3: Source Code

#### Imports (all files under `src/spec_orca/`)

- [ ] `__init__.py` — module docstring
- [ ] `cli.py` — docstring, argparse `prog=`, imports, commit message prefix
- [ ] `models.py` — docstring
- [ ] `backends.py` — imports, `SPEC_ORCHESTRATOR_BACKEND` env var
- [ ] `loader.py` — imports
- [ ] `orchestrator.py` — imports
- [ ] `protocols.py` — imports
- [ ] `stubs.py` — imports
- [ ] `dev/__init__.py` — docstring
- [ ] `dev/git.py` — logger name

### Phase 4: Tests

- [ ] `tests/test_cli.py` — imports, parser prog assertion, help assertion, mock paths
- [ ] `tests/test_e2e.py` — subprocess module path, output assertions
- [ ] `tests/test_backends.py` — imports, env var references in tests
- [ ] `tests/test_dev_git.py` — imports, logger name assertion
- [ ] `tests/test_orchestrator.py` — imports
- [ ] `tests/test_stubs.py` — imports
- [ ] `tests/test_loader.py` — imports
- [ ] `tests/test_models.py` — imports
- [ ] `tests/test_protocols.py` — imports

### Phase 5: Documentation

- [ ] `README.md` — title, tagline, package table, CLI examples, badge URL
- [ ] `CHANGELOG.md` — title, package reference, GitHub URLs
- [ ] `ARCHITECTURE.md` — title, product description, module map
- [ ] `CONTRIBUTING.md` — title, clone URL, mypy path
- [ ] `SECURITY.md` — product name references
- [ ] `LICENSE` — copyright holder name

### Phase 6: CI/CD

- [ ] `.github/workflows/ci.yml` — mypy source path

### Phase 7: Build/Dev Tools

- [ ] `noxfile.py` — docstring, SRC path constant

### Phase 8: GitHub Repository (manual, outside this repo)

- [ ] Repository name: `anthropics/spec-orchestrator` → `anthropics/spec-orca`
- [ ] Update all badge/link URLs after repo rename

## Environment Variables

| Current                      | Target                |
|------------------------------|-----------------------|
| `SPEC_ORCHESTRATOR_BACKEND`  | `SPEC_ORCA_BACKEND`   |
| `CLAUDE_CODE_EXECUTABLE`     | `CLAUDE_CODE_EXECUTABLE` (unchanged) |

Note: `CLAUDE_CODE_EXECUTABLE` is not project-specific and remains unchanged.

## Files Affected (Complete List)

```
src/spec_orchestrator/           → src/spec_orca/ (git mv)
├── __init__.py
├── backends.py
├── cli.py
├── dev/
│   ├── __init__.py
│   └── git.py
├── loader.py
├── models.py
├── orchestrator.py
├── protocols.py
└── stubs.py

tests/
├── test_backends.py
├── test_cli.py
├── test_dev_git.py
├── test_e2e.py
├── test_loader.py
├── test_models.py
├── test_orchestrator.py
├── test_protocols.py
└── test_stubs.py

Root files:
├── pyproject.toml
├── noxfile.py
├── LICENSE
├── README.md
├── CHANGELOG.md
├── ARCHITECTURE.md
├── CONTRIBUTING.md
└── SECURITY.md

CI:
└── .github/workflows/ci.yml
```

## Commit Strategy

Each phase above should be a separate, reviewable commit:

1. **Phase 1**: `git mv` package directory (preserves history)
2. **Phase 2**: Update pyproject.toml
3. **Phase 3**: Update source code imports and references
4. **Phase 4**: Update test imports and assertions
5. **Phase 5**: Update documentation
6. **Phase 6-7**: Update CI and dev tools

After each commit, verify: `ruff check && ruff format --check && mypy src/spec_orca && pytest`
