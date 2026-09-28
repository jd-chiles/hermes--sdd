# Sprint 5 requirements

## Functional requirements

### FR-01 — Close only completed work

The system must close only an unpaused project whose stage is `accepted`. Planned, dispatching, running, review, paused, and blocked projects must remain open and return an actionable error.

### FR-02 — Preserve history

Closing must append a lifecycle event, retain all prior task/attempt/evidence/event rows, and make the project identity immutable for historical inspection.

### FR-03 — Start the next request safely

After closure, initialization in the same repository must create a new active project identity. It must not delete, rewrite, or reuse the previous request’s task IDs or evidence.

### FR-04 — Enforce worker concurrency

Before a task becomes runnable, the plugin must atomically compare active reservations with `max_workers`. A rejected admission must leave ownership, lease, dispatch, and native state unchanged.

### FR-05 — Enforce runtime budgets

The plugin must reserve runtime before dispatch, record actual elapsed runtime at terminal receipt, and reject work that would exceed the configured total or per-task budget. Runtime accounting must survive restart.

### FR-06 — Persist blockers

Every admission denial must identify the violated limit, current usage, configured cap, and condition that can unblock it. Resume/recover may reevaluate the condition but must not reset counters.

### FR-07 — Guard host lifecycle integration

The plugin may call native interruption/review transitions only after a pinned-host capability check proves the command and response contract. Unsupported or ambiguous callbacks must fail closed.

## Non-functional requirements

- All admission mutations are SQLite transactions; JSONL remains a rebuildable export.
- Operation IDs are idempotent and payload-bound.
- Credentials and provider secrets are never persisted.
- Archived history is read-only through lifecycle APIs.
- Existing acceptance guarantees remain unchanged.
