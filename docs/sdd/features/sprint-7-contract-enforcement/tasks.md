# Sprint 7 task backlog

IDs are stable. Statuses reflect source inspection and prior local evidence, not new certification. Responsibility areas identify files to review, not assigned people or authorization to launch agents.

| ID | Priority | Deliverable / responsibility | Depends on | Requirements | Acceptance | Status and completion gate |
| --- | --- | --- | --- | --- | --- | --- |
| S7-01 | P0 | Dependency graph validation, transactional runnable admission, scheduler persistence/migration (`core.py`, `planning.py`, service) | — | FR-01, NFR-01, NFR-03, NFR-04 | AC-01, AC-02, AC-09, AC-10, AC-15 | Complete locally. Queued nodes use no slots and runnable admission is covered by the ordinary regression suite. |
| S7-02 | P0 | Attempt-bound receipt reducer, resource release, durable child scheduling (`core.py`, `bridge.py`, service) | S7-01 | FR-02, NFR-01, NFR-02, NFR-04 | AC-01, AC-02, AC-03, AC-11, AC-12, AC-18 | Complete locally for capacity completion and child promotion; native host receipt certification remains open. |
| S7-03 | P0 | Finalized criterion/check contract, Git baseline/diff scope, no-change outcome, contract migration (`planning.py`, `core.py`, schemas) | — | FR-03, FR-04, NFR-01, NFR-03 | AC-04, AC-05, AC-13, AC-14, AC-15 | Partial. Nonempty-submission guards exist; required spec checks, baseline attribution, revision invalidation, and justified no-change path remain open. Carries S6-07 and part of S6-08. |
| S7-04 | P0 | Explicit reviewer verdict and current-contract/attempt binding (`core.py`, schemas, review guidance) | S7-03 | FR-05, NFR-01, NFR-03 | AC-06, AC-07, AC-15 | Complete locally for structured approve/request_changes verdicts; full baseline-diff contract remains carry-forward. |
| S7-05 | P1 | Read-only scheduler/contract diagnostics and interface consistency (service, schemas, status/doctor) | S7-02, S7-04 | FR-06, NFR-02, NFR-04 | AC-16, AC-17 | Complete locally through status/doctor capacity, blocker, routing, and host-capability reporting. |
| S7-06 | P1 | Complete local evidence, independent review, packaging checks, and carry-forward report (`tests/`, docs) | S7-01, S7-02, S7-03, S7-04, S7-05 | FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, NFR-01, NFR-02, NFR-03, NFR-04 | AC-08 | Complete locally: 73 tests pass with no expected failures and modules compile; native certification remains separately tracked. |

## Delivery order

1. S7-01 and S7-03 can proceed independently; coordinate schema changes through one migration sequence.
2. S7-02 follows scheduler admission; S7-04 follows the verification contract.
3. S7-05 integrates diagnostics for both paths; S7-06 closes the local evidence gates.

Cross-sprint references are carry-forward mappings, not unresolved prerequisites. Existing Sprint 6 identity/accounting changes are the working-tree baseline. Host certification and broader lifecycle/public-interface work stay open in Sprint 6.

## Handoff for each task

Record changed files, requirement/acceptance IDs, exact commands and observed results, implementation revision or patch digest, migration impact, remaining limitations, and review findings. A task is complete only when its own gate passes. P1 work is required for sprint completion. A green unit-test summary alone cannot close missing matrix scenarios.
