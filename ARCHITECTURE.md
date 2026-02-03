# Architecture

This document describes the high-level design of **SpecOrca**.

## Overview

SpecOrca implements a two-role orchestration loop inspired by the
Architect / Agent pattern. A human (or automated caller) provides an initial
goal and project state. The system iterates between an Architect that plans and
an Agent that executes until the goal is met.

```
                ┌──────────────┐
                │  Project     │
                │  State &     │
                │  Goal        │
                └──────┬───────┘
                       │
                       ▼
              ┌────────────────┐
         ┌───▶│   Architect    │───┐
         │    └────────────────┘   │
         │      reads state,       │  emits specs
         │      decides next       │
         │      steps              │
         │                         ▼
         │    ┌────────────────┐
         │    │     Agent      │
         │    └───────┬────────┘
         │      picks spec,    │
         │      calls backend  │
         │                     │
         │    ┌────────────────┐
         └────│   Backend      │
              │  (Claude Code) │
              └────────────────┘
```

## Roles

### Architect

The Architect is responsible for **planning**. Given the current project state
and a high-level goal, it produces an ordered list of *specifications* — small,
verifiable units of work. Each specification describes:

- **What** needs to change (files, interfaces, behaviour).
- **Acceptance criteria** the Agent must satisfy.
- **Dependencies** on prior specs (if any).

The current SimpleArchitect is deterministic and non-LLM. It loads the YAML
spec file once, orders specs by dependencies, and updates spec status and
attempts as results arrive. It does not generate new specs at runtime.

### Agent

The Agent is responsible for **execution**. It takes a single specification,
invokes the coding backend to carry out the work, and reports a structured
result (success, failure, or partial progress). The Agent does not decide
*what* to do — it follows the Architect's spec.

## Backend interface

The coding backend is the component that performs the actual code changes. It is
defined as a Python protocol:

```python
class Backend(Protocol):
    def execute(self, spec: Spec, context: Context) -> Result: ...
```

Implementations include a deterministic mock backend for tests and a Claude
Code backend that shells out to the `claude` CLI. The CLI defaults to the mock
backend for deterministic runs. Any object satisfying the `Backend` protocol
can be substituted — for example, a backend that calls a different LLM, runs a
local script, or applies a deterministic code transform.

## Orchestration loop

The top-level loop ties everything together:

1. **Initialise** — Load project state and goal from the user.
2. **Plan** — Architect produces / updates the spec queue.
3. **Execute** — Agent takes the next spec, calls the backend.
4. **Record** — Result is appended to the project state.
5. **Evaluate** — Architect reviews updated state. If the goal is met (or a
   stop condition is reached), exit. Otherwise go to step 2.

### State and spec inputs

- **Project state** is a structured snapshot of the repository: file tree,
  recent diffs, test results, and any prior spec outcomes. It is rebuilt (or
  incrementally updated) before each Architect cycle.
- **Goal** is a free-text description provided by the user at startup.
- **Specs** are structured objects that the Architect emits and the Agent
  consumes.

## Module map

```
src/spec_orca/
|-- __init__.py          # package version
|-- cli.py               # argument parsing, entry point
|-- architect.py         # SimpleArchitect (deterministic YAML planner)
|-- agent.py             # Agent role
|-- orchestrator.py      # orchestration loop + summaries
|-- backend.py           # Backend protocol
|-- backends/
|   |-- __init__.py      # backend factory
|   |-- mock.py          # deterministic mock backend
|   `-- claude.py        # Claude Code backend (subprocess)
|-- spec.py              # YAML spec loader + validation
|-- models.py            # Spec, Result, Context models
|-- state.py             # project state snapshotting
|-- dev/
|   `-- git.py           # opt-in auto-commit helper
|-- loader.py            # spec loader (Markdown/YAML detection)
|-- protocols.py         # step-based protocols
|-- stubs.py             # step-based stubs for testing
`-- _deprecated_cli.py   # compatibility wrapper
```
