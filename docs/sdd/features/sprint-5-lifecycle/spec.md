# Sprint 5 — request lifecycle and project history

- Mode: `feature`
- Specification revision: `1`
- Delivery boundary: verified local repository change; no automatic commit, PR, deployment, or publication.

## Objective

Allow an accepted SDD request to be explicitly closed and a subsequent request to start in the same repository while preserving the prior ledger, evidence, task graph, and acceptance history.

## Stable task graph

- **S5-01** — Add an explicit close operation requiring accepted, unpaused project state.
- **S5-02** (depends on S5-01) — Archive the closed project identity without deleting historical records and initialize a new active request.
- **S5-03** (depends on S5-01, S5-02) — Add command/tool surfaces and restart/history regression coverage.

## Acceptance criteria

- Closing a planned, running, paused, or review project is rejected with an actionable reason.
- Closing an accepted project records an immutable lifecycle event and marks it closed.
- A new request after closure creates a new active project identity in the same repository.
- Prior attempts, evidence, events, and task rows remain in SQLite and JSONL history.
- Repeated close requests are idempotent and do not mutate the closed project.
