# Changelog

All notable changes to **SpecOrca** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Renamed project from `spec-orchestrator` to **SpecOrca**.
  - Display name: SpecOrca
  - CLI command: `spec-orca`
  - Python package: `spec_orca`
  - Environment variable prefix: `SPEC_ORCA_`

### Added

- Project scaffold: `src/spec_orca` package with CLI entry point.
- `spec-orca --help` and `--version` commands.
- Developer tooling: ruff (lint + format), mypy (strict), pytest + coverage,
  pre-commit hooks, nox task runner.
- Repository documentation: README, ARCHITECTURE, CONTRIBUTING, CHANGELOG,
  CODE_OF_CONDUCT, SECURITY.
- YAML spec loader with validation for goals and specs.
- Deterministic orchestration loop (SimpleArchitect + Agent) with dependency
  ordering and explicit results.
- CLI commands: `run`, `plan`, and `doctor`.
- Backends: deterministic mock backend and Claude Code backend.
- Claude Code backend integration (CLI config, validation, and structured output).
- Project state snapshots with git summaries persisted to state.json.
- Opt-in auto-commit helper that stages tracked changes only.
- `spec-orca init` command for scaffolding spec files.
- `--allow-all` flag for granting Claude Code full tool access.
- Live progress output during orchestration runs.
- Resilient structured output handling when Claude runs out of turns.

## [0.1.0] - 2026-02-02

### Added

- Initial package release with minimal CLI skeleton.

[Unreleased]: https://github.com/anthropics/spec-orchestrator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/anthropics/spec-orchestrator/releases/tag/v0.1.0
