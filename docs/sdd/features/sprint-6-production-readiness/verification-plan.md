# Sprint 6 verification plan

## Baseline and evidence policy

Baseline commit: `bb9381df05986f759dccd94d6a89f49a40ebb92f`. The earlier review observed 53 passing local Linux tests and the failures recorded in [the spec](spec.md). This package introduces no implementation fixes and does not certify a host or candidate.

Use [the acceptance matrix](acceptance-matrix.md) as the coverage ledger. Every evidence record identifies its source revision and environment. Temporary review probes must become regression cases under S6-02; existing successful tests are not substitutes for the missing scenarios.

## Gate 1 — Deterministic local regressions

Run the repository's existing commands after implementation changes:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q sdd_hermes scripts
git diff --check
```

Extend the existing acceptance, coordination, command, and packaging tests; add migration and real-Git diff fixtures where needed. Test public service paths as well as ledger primitives. Reproduce observed defects before fixing them, then retain the cases. Avoid writing tests that merely restate SQL or mock every meaningful behavior.

Required fixture groups:

- Scheduler: all workflow sizes, parent dependencies, worker cap, promotion, automatic completion release, and no accidental launch during graph creation.
- Failure injection: terminate before intent, after intent, after native creation, before receipt persistence, and during export; restart/reconcile each point.
- Accounting: consumed total cap, cumulative per-task cap, concurrent workers, failed attempts, unknown elapsed time, and overrun.
- Lifecycle: ten requests, identical replays, repeated titles, concurrent initialization, terminal mutations, stale acceptance at close, and abandonment.
- Acceptance: predefined checks, spec revision, missing/renamed/deleted/untracked files, dirty baselines, reviewer verdict/identity, and no-change outcomes.
- Migration: populated schema-v5 active and historical data, duplicate/ambiguous roots, interrupted migration, repeated migration, and future schema refusal.
- Interfaces: invalid inputs, help/typos, failure exit codes, human/JSON output, tool manifest parity, and side-effect-free diagnostics.
- Packaging: equivalent path spellings/parent aliases, deterministic output, output-inside-source, and source symlink rejection.

Use isolated temporary repositories, homes, boards, and profiles. Never rely on user credentials, modify real profile configuration, or dispatch live work from unit tests.

## Gate 2 — Pinned host contract

S6-01 selects exact supported host revisions and records their documented public APIs. Probe actual native behavior for task creation versus launch, dependency release, idempotency, attempt identity, terminal receipts, elapsed runtime, interruption/deadlines, review transition, and CLI dispatch. The existing `host_routing_contract.py` checks source flags/argv only; it cannot certify lifecycle or provider execution.

Capability outcomes are `verified`, `unsupported`, or `unverified`, with supporting receipts. If a necessary capability is absent, keep the feature blocked or explicitly revise supported-host scope. Do not invent flags or conclude that profile names prove support. Record deadline precision/overrun behavior and polling bounds before making a hard-runtime claim.

## Gate 3 — Candidate artifact and platform CI

Build a candidate from the exact revision using the packaging script:

```bash
python3 scripts/package_release.py --output artifact/hermes-sdd-team.tar.gz
python3 scripts/host_smoke.py
```

These commands exist today. `host_smoke.py` currently rebuilds an artifact and runs doctor/validation; S6-11 must add a way to certify the exact already-built candidate digest and run the broader lifecycle suite. Do not report the current smoke test as end-to-end coverage.

For Linux, macOS, and Windows/WSL2, explicitly distinguish native Python/package checks from the supported Hermes runtime environment. Record exact OS, Python, and host versions. Install pinned host revisions through a reproducible setup; do not use an unpinned latest installer as certification. Preserve independent per-platform host job scheduling and aggregate all required gates before readiness.

Extract the candidate outside the source checkout, install into an isolated Hermes home, and exercise:

1. Doctor and plugin validation, manifest parity, and existing-profile preservation.
2. Public CLI and slash execution of a small bugfix, feature, and product fixture with actual worker receipts.
3. Pause/interruption, restart/recovery, provider/task failure simulation at the supported boundary, and resource reconciliation.
4. Acceptance and close; multiple subsequent requests; history and abandonment.
5. Upgrade a populated schema-v5 ledger and continue or present the expected legacy-contract blocker.
6. Uninstall without removing user work or unrelated profile settings.

Use authorized test credentials where actual model execution is required; missing credentials are a blocker for those scenarios, not permission to substitute mocks. Capture bounded sanitized logs and publish no credentials in CI artifacts.

## Gate 4 — User walkthrough and release-candidate report

Follow the README from a fresh home using an immutable real candidate reference selected during implementation, without undocumented manual steps. Confirm exact commands, expected progress, error remedies, and uninstall behavior. Record the supported-host/platform matrix, artifact checksum, version/changelog, all acceptance-row outcomes, and any limitations.

An independent reviewer checks the diff and evidence against this package. The go/no-go report may say ready only when every required row passes for the advertised support scope. Candidate preparation does not authorize release publication.

## Validation of this documentation change

Check relative Markdown links, requirement/task/acceptance ID traceability, dependency references and cycles, and `git diff --check`. Runtime tests are unnecessary solely for this documentation addition. Record implementation test results only after the corresponding work is performed.
