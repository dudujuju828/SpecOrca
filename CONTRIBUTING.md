# Contributing to SpecOrca

Thank you for considering a contribution. This guide covers local setup,
running checks, and what we look for in pull requests.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## Local setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/anthropics/spec-orchestrator.git
   cd spec-orchestrator
   ```

2. **Create a virtual environment** (recommended)

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux / macOS
   .venv\Scripts\activate      # Windows
   ```

3. **Install in editable mode with dev dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**

   ```bash
   pre-commit install
   ```

5. **Verify the CLI works**

   ```bash
   spec-orca --version          # should print: spec-orca 0.1.0
   spec-orca --help             # show available commands
   spec-orca run --help         # show run subcommand options
   ```

## Local development workflow

After installing in editable mode (`pip install -e ".[dev]"`), changes to
source files under `src/spec_orca/` take effect immediately — no reinstall
needed.

### Running the CLI

```bash
# Via the installed console script
spec-orca run --spec path/to/spec.md --backend mock

# Or via python -m (useful if the script isn't on PATH)
python -m spec_orca.cli run --spec path/to/spec.md --backend mock
```

### Running checks

All quality checks are managed by [nox](https://nox.thea.codes/):

```bash
nox                    # run all: fmt, lint, typecheck, tests
nox -s fmt             # auto-format with ruff
nox -s lint            # lint with ruff
nox -s typecheck       # type-check with mypy (strict)
nox -s tests           # run pytest with coverage
```

You can also run the tools directly:

```bash
ruff format .                  # auto-format
ruff check .                   # lint
mypy src/spec_orca             # type-check (strict)
pytest                         # test + coverage
```

### Required pipeline (before every commit)

Every commit must leave the repo green. Run the full pipeline:

```bash
ruff format . && ruff check . && mypy src/spec_orca && pytest
```

Or equivalently:

```bash
nox
```

## Current pipeline status

| Check       | Tool                | Command               | Target      |
|-------------|---------------------|-----------------------|-------------|
| Format      | ruff format         | `ruff format .`       | No changes  |
| Lint        | ruff check          | `ruff check .`        | 0 errors    |
| Type check  | mypy (strict)       | `mypy src/spec_orca`  | 0 errors    |
| Tests       | pytest + coverage   | `pytest`              | >= 80% cov  |

## Style guide

- **Formatting**: ruff format, line length 99.
- **Linting**: ruff with pyflakes, pycodestyle, isort, pep8-naming, pyupgrade,
  bugbear, builtins, comprehensions, simplify, and ruff-specific rules.
- **Typing**: all public APIs must have type annotations. mypy runs in strict
  mode.
- **Tests**: every new feature or bug fix should include tests. Coverage must
  stay at or above 80%.

## Commit discipline

- Write clear, imperative-mood commit messages ("Add X", not "Added X").
- Keep commits focused — one logical change per commit.
- Reference related issues where applicable (`Fixes #123`).
- **Every commit must leave the working tree clean and all checks passing.**
  Run `nox` (or the direct commands above) before committing.
- Do not commit with failing lint, type errors, or test failures.

## Pull requests

1. Fork the repository and create a feature branch from `main`.
2. Make your changes with tests.
3. Run `nox` to verify all checks pass.
4. Open a PR with a short description of what changed and why.
5. A maintainer will review and may request changes.

## Reporting issues

- **Bugs and feature requests**: open a GitHub issue.
- **Security vulnerabilities**: see [SECURITY.md](SECURITY.md).
