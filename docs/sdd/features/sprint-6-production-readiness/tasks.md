# Sprint 6 task backlog

All tasks are open. IDs remain stable across implementation changes. Owners below are responsibility areas, not assigned people or authorization to dispatch agents. Independent tasks may be implemented separately; dependencies are completion prerequisites.

| ID | Priority | Deliverable / ownership area | Depends on | Requirements | Completion gate |
| --- | --- | --- | --- | --- | --- |
| S6-01 | P0 | Pin host contract and capability inventory (`bridge.py`, host scripts) | — | FR-02, FR-03, FR-10, FR-12 | Record exact host revision and real create/start/terminal/pause/deadline/CLI receipts or explicit unsupported results; settle D-03 questions **Blocked: installed host cannot start (`ruamel.yaml` missing); source inventory recorded.** |
| S6-02 | P0 | Commit regression fixtures for review findings (`tests/`) | — | FR-01, FR-03, FR-04, FR-08, FR-09 | Reproduce the five-task cap, consumed-budget admission, second/third request collision, empty/no-op acceptance, and equivalent-output-path packaging cases; tests fail for the intended reason before fixes **Implemented; pending failures retained as expected-failure tests.** |
| S6-03 | P0 | Active request association and schema migration (`core.py`) | S6-02 | FR-04, NFR-01, NFR-02 | Populated v5 fixtures migrate safely; repeated initialization resolves current identity; atomic association and namespaced artifacts tested **Implemented locally; 5 migration tests pass.** |
| S6-04 | P0 | Dependency-aware scheduler (`__init__.py`, `core.py`, `bridge.py`) | S6-01, S6-02, S6-03 | FR-01, FR-02, NFR-01 | Full graph is durable; only runnable admitted workers consume slots; every launch/promotion path obeys shared admission |
| S6-05 | P0 | Receipt reconciliation and runtime enforcement (`bridge.py`, `core.py`) | S6-04 | FR-02, FR-03, NFR-01, NFR-03 | Automatic capacity release, duplicate/out-of-order receipt handling, cumulative budgets, restart, unknown duration, and overruns pass **Runtime accounting implemented locally; native receipt release still open.** |
| S6-06 | P0 | Close/abandon/history transitions (`core.py`, service layer) | S6-03, S6-05, S6-08 | FR-04, FR-05 | Ten-request sequence and terminal mutation rejection pass; close revalidates acceptance; abandon retains evidence and waits for worker reconciliation |
| S6-07 | P0 | Versioned verification contract and baseline diff (`planning.py`, `core.py`) | S6-02, S6-03 | FR-06, FR-07, NFR-02 | Finalized criterion/check mappings and change attribution persist; explicit revisions invalidate affected evidence; legacy and unsupported cases block honestly |
| S6-08 | P0 | Explicit review and acceptance outcomes (`core.py`, schemas, skills) | S6-07 | FR-06, FR-07, FR-08 | Required-check/diff/verdict gates pass; justified no-change outcome is distinct; existing stale-evidence guarantees remain green **Partial: empty implementation/check submissions now reject; explicit verdict and full spec-bound contract remain Sprint 7.** |
| S6-09 | P1 | Portable artifact construction (`scripts/package_release.py`, tests) | S6-02 | FR-09 | Equivalent output paths never enter archive; deterministic hashes and manifest/tool/version parity pass across supported platforms **Output-path fix and regression coverage implemented locally.** |
| S6-10 | P1 | Public commands and actionable diagnostics (`__init__.py`, `plugin.yaml`) | S6-01, S6-05, S6-06, S6-08 | FR-11, FR-12 | CLI dispatch, exit codes, human/JSON views, history/abandon/help, typo handling, and capability-aware doctor are verified |
| S6-11 | P1 | Candidate CI and host certification (`.github/workflows/`, scripts) | S6-05, S6-06, S6-08, S6-09, S6-10 | FR-09, FR-10, NFR-02, NFR-03 | Candidate digest passes clean install, complete workflows, recovery, profile preservation, and upgrade for every advertised target |
| S6-12 | P1 | Quickstart and release-candidate handoff (`README.md`, release docs) | S6-10, S6-11 | FR-10, FR-12 | Fresh-home walkthrough passes; exact install ref and compatibility report recorded; changelog/checksums and go/no-go report prepared |

## Delivery sequence

1. Establish host facts and failing regression cases (S6-01–02).
2. Repair identity/persistence, then scheduling/accounting and acceptance (S6-03–08). Packaging repair S6-09 can proceed independently after its regression case exists.
3. Complete public commands, certify the candidate, and verify onboarding (S6-10–12).

P0 tasks repair core product guarantees. P1 tasks remain required for sprint acceptance; their priority does not make release quality optional. A host blocker permits useful local implementation but does not close a host-dependent task.

## Task handoff contract

Each task records changed files, requirement/acceptance IDs addressed, exact verification commands and results, artifact/host identifiers where relevant, unresolved limitations, and an independent review verdict. Report local and native-host evidence separately. Update this backlog's status only when its completion gate is met.
