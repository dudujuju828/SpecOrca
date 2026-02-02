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

## Running checks

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
ruff check .                   # lint
ruff format .                  # format
mypy src/spec_orca             # type-check
pytest                         # test + coverage
```

## Style guide

- **Formatting**: ruff format, line length 99.
- **Linting**: ruff with pyflakes, pycodestyle, isort, pep8-naming, pyupgrade,
  bugbear, builtins, comprehensions, simplify, type-checking, and ruff-specific
  rules.
- **Typing**: all public APIs must have type annotations. mypy runs in strict
  mode.
- **Tests**: every new feature or bug fix should include tests. Coverage must
  stay at or above 80%.

## Commit expectations

- Write clear, imperative-mood commit messages ("Add X", not "Added X").
- Keep commits focused — one logical change per commit.
- Reference related issues where applicable (`Fixes #123`).
- Make sure `nox` passes before pushing.

## Pull requests

1. Fork the repository and create a feature branch from `main`.
2. Make your changes with tests.
3. Run `nox` to verify all checks pass.
4. Open a PR with a short description of what changed and why.
5. A maintainer will review and may request changes.

## Reporting issues

- **Bugs and feature requests**: open a GitHub issue.
- **Security vulnerabilities**: see [SECURITY.md](SECURITY.md).
