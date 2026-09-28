# Sprint 7 — contract enforcement

Status: implemented locally, 2026-09-28. Local verification is green; native host certification remains pending.

Sprint 7 completes runnable-only dependency admission and strengthens the receipt, runtime, and review contracts. The scheduler regression is now an ordinary pass, and reviewer verdicts are persisted as structured ledger records.

## Development package

- [Specification and baseline](../sdd/features/sprint-7-contract-enforcement/spec.md)
- [Requirements](../sdd/features/sprint-7-contract-enforcement/requirements.md)
- [Architecture and migration](../sdd/features/sprint-7-contract-enforcement/architecture.md)
- [Task backlog](../sdd/features/sprint-7-contract-enforcement/tasks.md)
- [Acceptance matrix](../sdd/features/sprint-7-contract-enforcement/acceptance-matrix.md)
- [Verification plan](../sdd/features/sprint-7-contract-enforcement/verification-plan.md)
- [Decision log](../sdd/features/sprint-7-contract-enforcement/decision-log.md)

## Delivery and status

| Tasks | Outcome | Status |
| --- | --- | --- |
| S7-01–02 | Runnable-only admission, receipt-driven completion, automatic child scheduling | Complete locally; native host receipt certification remains open |
| S7-03–04 | Submission guards and explicit review verdicts | Partial for full no-change/baseline-diff contract; verdict enforcement complete |
| S7-05 | Read-only human/JSON diagnostics with actionable blockers | Complete locally through status/doctor blockers |
| S7-06 | Complete local verification, independent review, carry-forward report | Complete locally: 73 tests pass and modules compile |

S7-01 and S7-03 may proceed independently; receipts and review follow their respective prerequisites. Diagnostics and aggregate verification follow both paths. Existing Sprint 6 references are carry-forward mappings, not prerequisites requiring the same unfinished work twice.

## Exit criteria

- All implemented acceptance rows have local evidence for the implementation revision.
- Both original Sprint 6 regression cases are ordinary passes.
- Bugfix, feature, and product graphs finish through simulated receipt-driven scheduling under default limits.
- Required spec checks, complete request-diff coverage, and current independent approval control acceptance.
- Migration preserves historical data and blocks unsupported legacy evidence honestly.
- Local suite, compilation, diff, and packaging checks pass; skipped/expected failures do not satisfy required scenarios.

The sprint is intentionally local. Native lifecycle certification and host environment repair remain in Sprint 6. Local completion does not establish production host support.
