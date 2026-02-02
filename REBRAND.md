# Rebrand Plan: spec-orchestrator → SpecOrca

This document defines the target naming conventions and provides a complete
checklist of all name surfaces that must be updated during the rebrand.

## Status: COMPLETE

The rebrand from `spec-orchestrator` to `SpecOrca` has been completed.

## Final Naming Decisions

| Surface              | Old Value                | New Value          |
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

## Backwards Compatibility (Alias Policy)

Deprecated aliases are provided for a smooth migration:

### Import Aliases
- `import spec_orchestrator` → forwards to `spec_orca` with `DeprecationWarning`
- All submodules (`backends`, `models`, `cli`, etc.) forward with warnings
- Warnings are issued once per module import

### CLI Alias
- `spec-orchestrator` command → prints warning to stderr, forwards to `spec-orca`

### Removal Timeline
- Aliases will be removed in a future major release
- Users should migrate to the new names promptly

## Checklist

### Phase 1: Package Directory (requires `git mv`)

- [x] `src/spec_orchestrator/` → `src/spec_orca/`

### Phase 2: pyproject.toml

- [x] `name = "spec-orchestrator"` → `name = "spec-orca"`
- [x] `authors` attribution text
- [x] `[project.scripts]` entry point: `spec-orchestrator` → `spec-orca`
- [x] `[tool.ruff.lint.isort]` known-first-party
- [x] `[tool.mypy]` packages
- [x] `[tool.pytest.ini_options]` --cov target
- [x] `[tool.coverage.run]` source

### Phase 3: Source Code

#### Imports (all files under `src/spec_orca/`)

- [x] `__init__.py` — module docstring
- [x] `cli.py` — docstring, argparse `prog=`, imports, commit message prefix
- [x] `models.py` — docstring
- [x] `backends.py` — imports, `SPEC_ORCA_BACKEND` env var
- [x] `loader.py` — imports
- [x] `orchestrator.py` — imports
- [x] `protocols.py` — imports
- [x] `stubs.py` — imports
- [x] `dev/__init__.py` — docstring
- [x] `dev/git.py` — logger name

### Phase 4: Tests

- [x] `tests/test_cli.py` — imports, parser prog assertion, help assertion, mock paths
- [x] `tests/test_e2e.py` — subprocess module path, output assertions
- [x] `tests/test_backends.py` — imports, env var references in tests
- [x] `tests/test_dev_git.py` — imports, logger name assertion
- [x] `tests/test_orchestrator.py` — imports
- [x] `tests/test_stubs.py` — imports
- [x] `tests/test_loader.py` — imports
- [x] `tests/test_models.py` — imports
- [x] `tests/test_protocols.py` — imports
- [x] `tests/test_deprecated_aliases.py` — NEW: tests for backwards-compat shims

### Phase 5: Documentation

- [x] `README.md` — title, tagline, package table, CLI examples, badge URL
- [x] `CHANGELOG.md` — title, package reference, GitHub URLs
- [x] `ARCHITECTURE.md` — title, product description, module map
- [x] `CONTRIBUTING.md` — title, clone URL, mypy path
- [x] `SECURITY.md` — product name references
- [ ] `LICENSE` — copyright holder name (optional, kept as-is)

### Phase 6: CI/CD

- [x] `.github/workflows/ci.yml` — mypy source path

### Phase 7: Build/Dev Tools

- [x] `noxfile.py` — docstring, SRC path constant

### Phase 8: GitHub Repository (manual, outside this repo)

- [ ] Repository name: update if desired (not required)
- [ ] Update all badge/link URLs after repo rename (if applicable)

## Environment Variables

| Old                          | New                   | Status    |
|------------------------------|-----------------------|-----------|
| `SPEC_ORCHESTRATOR_BACKEND`  | `SPEC_ORCA_BACKEND`   | Changed   |
| `CLAUDE_CODE_EXECUTABLE`     | `CLAUDE_CODE_EXECUTABLE` | Unchanged |

Note: `CLAUDE_CODE_EXECUTABLE` is not project-specific and remains unchanged.

## Files Changed

### New Package Structure
```
src/spec_orca/                   # Primary package (NEW)
├── __init__.py
├── _deprecated_cli.py           # Deprecated CLI entry point (NEW)
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

src/spec_orchestrator/           # Backwards-compat shims (NEW)
├── __init__.py                  # Re-exports spec_orca with warning
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
```

### Test Files
```
tests/
├── test_backends.py             # Updated imports
├── test_cli.py                  # Updated imports and assertions
├── test_deprecated_aliases.py   # NEW: tests for shims
├── test_dev_git.py              # Updated imports
├── test_e2e.py                  # Updated subprocess paths
├── test_loader.py               # Updated imports
├── test_models.py               # Updated imports
├── test_orchestrator.py         # Updated imports
├── test_protocols.py            # Updated imports
└── test_stubs.py                # Updated imports
```

## Verification

All quality checks pass:
- `ruff format .` — no changes needed
- `ruff check .` — all checks passed
- `mypy src/spec_orca` — no issues found
- `pytest` — 144 passed, 1 skipped, 95% coverage
