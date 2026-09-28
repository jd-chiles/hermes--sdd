# Sprint 5 — request lifecycle and operational limits

Status: implementation baseline, 2026-09-28; remaining work is carried into [Sprint 6](sprint-6.md). Lifecycle and local operational-limit slices have local test evidence; native host certification remains open. The [Sprint 6 review baseline](../sdd/features/sprint-6-production-readiness/spec.md) records additional lifecycle and budget defects, so the delivered slices below must not be read as complete production guarantees.

## Delivered this cycle

- Added `sdd_close`, `/sdd close`, and `hermes sdd close`.
- Close requires an unpaused accepted project.
- Close is idempotent and records `project_closed`.
- Closed projects are archived by identity, preserving prior SQLite rows and JSONL history.
- A new request can initialize in the same repository without deleting the previous request.
- Added restart/history and lifecycle regression coverage.
- Added schema v5 worker/runtime reservations, durable limit blockers, and restart-safe capacity accounting.
- Native dispatch now reserves worker/runtime capacity before creating a task; terminal completion releases capacity and records actual runtime.
- Added `sdd_complete_task` for explicit terminal accounting and status visibility for reservations/blockers.

The complete development package is in [`docs/sdd/features/sprint-5-lifecycle/`](../sdd/features/sprint-5-lifecycle/): requirements, architecture, acceptance matrix, verification plan, and decision log.

## Next backlog

| ID | Priority | Deliverable | Status |
| --- | --- | --- | --- |
| S5-04 | P1 | Enforce max workers atomically at admission/dispatch boundaries. | Implemented locally; host lifecycle release integration open |
| S5-05 | P1 | Enforce total and per-task runtime budgets with durable accounting. | Implemented locally; host elapsed-time receipt integration open |
| S5-06 | P1 | Add native lifecycle callbacks for task interruption and review transitions. | Open; host contract required |
| S5-07 | P2 | Add lifecycle/history status views and archived-project diagnostics. | Open |
| S5-08 | P2 | Define managed dependency and browser-evidence contracts. | Deferred |

## Exit criteria

- Accepted requests can be closed without mutating historical evidence.
- New requests can start in the same repository with a new project identity.
- Operational limits are enforced, not merely displayed.
- Native lifecycle behavior is verified against a pinned Hermes host before claiming support.

## Sprint package acceptance

- The spec identifies delivered versus planned work and stable task IDs.
- Requirements define functional, non-functional, compatibility, and security boundaries.
- Architecture places all limit decisions before native dispatch and keeps SQLite authoritative.
- The acceptance matrix maps each requirement to deterministic evidence.
- The verification plan separates local evidence from pinned-host certification.

## Current verification

- Local suite: 53 tests passed.
- Python compilation and diff checks passed.
- Capacity controls are covered for concurrent admission, total-runtime denial, restart persistence, idempotent completion, and pre-dispatch enforcement.
- Native lifecycle callback verification remains blocked on the pinned-host contract and installed Hermes runtime availability.
