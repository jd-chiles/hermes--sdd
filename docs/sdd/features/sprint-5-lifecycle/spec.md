# Sprint 5 — request lifecycle and operational limits

- Mode: `feature`
- Specification revision: `1`
- Delivery boundary: verified local repository change; no automatic commit, PR, deployment, or publication.

## Objective

Make SDD usable as a persistent repository workflow: accepted requests can be closed without losing evidence, subsequent requests can start safely, and configured worker/runtime limits are enforced at the plugin admission boundary.

## Baseline

The request lifecycle slice is already implemented locally: `sdd_close`, close idempotency, closed-project archiving, same-repository reinitialization, and history-preservation tests. This sprint specification treats those behaviors as S5-01 through S5-03 and drives the remaining operational work.

## Scope

In scope:

- Explicit close and new-request lifecycle.
- Historical project identity and read-only preservation.
- Maximum worker admission.
- Total runtime and per-task runtime admission/recording.
- Durable blockers and status visibility for limit denials.
- Host lifecycle callback contract discovery and guarded integration.

Out of scope:

- Automatic commits, pull requests, deployment, or publication.
- Managed dependency installation and browser evidence adapters.
- Organization-wide dashboards or centralized policy administration.
- Claiming native lifecycle support before the pinned Hermes host contract passes.

## Stable task graph

- **S5-01** — Add an explicit close operation requiring accepted, unpaused project state. **Delivered.**
- **S5-02** (depends on S5-01) — Archive the closed project identity without deleting historical records and initialize a new active request. **Delivered.**
- **S5-03** (depends on S5-01, S5-02) — Add command/tool surfaces and restart/history regression coverage. **Delivered.**
- **S5-04** (P1; depends on S5-03) — Enforce `max_workers` atomically at dispatch/ownership admission and persist a blocker when the limit is reached. **Implemented locally.**
- **S5-05** (P1; depends on S5-04) — Enforce total runtime and per-task runtime budgets using durable reservations and completion accounting. **Implemented locally.**
- **S5-06** (P1; depends on S5-04) — Probe the pinned host for lifecycle callbacks and integrate only supported task-interruption/review transitions.
- **S5-07** (P2; depends on S5-04, S5-05) — Add history-aware status views and selected-project diagnostics without exposing mutable archived state.

## Acceptance criteria

- Closing a planned, running, paused, or review project is rejected with an actionable reason.
- Closing an accepted project records an immutable lifecycle event and marks it closed.
- A new request after closure creates a new active project identity in the same repository.
- Prior attempts, evidence, events, and task rows remain in SQLite and JSONL history.
- Repeated close requests are idempotent and do not mutate the closed project.
- Concurrent dispatch admission cannot exceed `max_workers`.
- Runtime denials persist an actionable blocker and do not consume a native attempt.
- Restarting the service preserves worker reservations, runtime accounting, and blockers.
- Unsupported host lifecycle callbacks fail visibly and leave native state unchanged.

## Success measures

- Zero accepted requests lose attempts or evidence after close/reinitialize.
- Zero dispatches pass the worker limit through concurrent coordinators.
- Every limit denial is visible in `sdd_status` with the limit and unblock condition.
- Host lifecycle support is reported as verified, unsupported, or unverified—never inferred from profile names.
