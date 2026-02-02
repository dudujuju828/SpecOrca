# Architecture

This document describes the high-level design of **spec-orchestrator**.

## Overview

`spec-orchestrator` implements a two-role orchestration loop inspired by the
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

The Architect re-evaluates after every Agent cycle, so specifications can be
added, reordered, or dropped as the project evolves.

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

The **default backend** shells out to `claude-code` (the Claude Code CLI),
passing the spec as a prompt and collecting the result. Any object satisfying
the `Backend` protocol can be substituted — for example, a backend that calls a
different LLM, runs a local script, or applies a deterministic code transform.

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
src/spec_orchestrator/
├── __init__.py          # package version
├── cli.py               # argument parsing, entry point
├── (orchestrator.py)    # orchestration loop        [planned]
├── (architect.py)       # Architect role             [planned]
├── (agent.py)           # Agent role                 [planned]
├── (backend.py)         # Backend protocol + default [planned]
├── (models.py)          # Spec, Result, Context      [planned]
└── (state.py)           # project state management   [planned]
```

Items in parentheses are planned modules not yet implemented.
