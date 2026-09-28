# Sprint 5 — request lifecycle and operational limits

Status: active, 2026-09-28. Lifecycle slice implemented locally; broader limit enforcement remains next.

## Delivered this cycle

- Added `sdd_close`, `/sdd close`, and `hermes sdd close`.
- Close requires an unpaused accepted project.
- Close is idempotent and records `project_closed`.
- Closed projects are archived by identity, preserving prior SQLite rows and JSONL history.
- A new request can initialize in the same repository without deleting the previous request.
- Added restart/history and lifecycle regression coverage.

## Next backlog

| ID | Priority | Deliverable | Status |
| --- | --- | --- | --- |
| S5-04 | P1 | Enforce max workers and total runtime at admission/dispatch boundaries. | Open |
| S5-05 | P1 | Add native lifecycle callbacks for task interruption and review transitions. | Open; host contract required |
| S5-06 | P2 | Add lifecycle/history status views and request selection for archived projects. | Open |
| S5-07 | P2 | Define managed dependency and browser-evidence contracts. | Open |

## Exit criteria

- Accepted requests can be closed without mutating historical evidence.
- New requests can start in the same repository with a new project identity.
- Operational limits are enforced, not merely displayed.
- Native lifecycle behavior is verified against a pinned Hermes host before claiming support.
