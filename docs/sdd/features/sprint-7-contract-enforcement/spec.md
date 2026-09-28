# Sprint 7 — contract enforcement

- Mode: `feature`
- Specification revision: `2`
- Updated: `2026-09-28`
- Status: full draft; implementation partially started, sprint acceptance pending.
- Baseline: the current working tree on top of `bb9381df05986f759dccd94d6a89f49a40ebb92f`, including uncommitted Sprint 6 changes. That commit alone does not contain the baseline implementation.
- Delivery boundary: local, reviewable changes and evidence only; native host certification, commits, PRs, and publication are separate actions.

## Objective

Turn the remaining Sprint 6 expected failures into enforced guarantees: runnable scheduling must respect dependencies and worker reservations, and acceptance must require a real implementation scope with meaningful review evidence.

## Package index

- [Requirements](requirements.md): functional and non-functional contracts.
- [Architecture](architecture.md): state transitions, persistence, interfaces, and migration.
- [Task backlog](tasks.md): stable task IDs, dependencies, and completion gates.
- [Acceptance matrix](acceptance-matrix.md): requirement and task traceability.
- [Verification plan](verification-plan.md): fixtures, evidence, and local exit gates.
- [Decision log](decision-log.md): chosen boundaries and unresolved host questions.
- [Sprint summary](../../../sprints/sprint-7.md): current status and delivery order.

## Baseline and existing evidence

The latest reported local run discovered 72 tests: 71 ordinary passes and one expected failure. This is historical evidence from the preceding implementation turn, not a new run for this documentation revision.

Already present in the working tree:

- Schema v6 request identities, migration backups/rollback coverage, cumulative runtime accounting, and packaging output-path fixes from Sprint 6.
- Acceptance rejects engineer submissions with empty file scope or no declared checks. The empty/no-op regression in `tests/test_sprint6_pending.py` is now an ordinary test.
- Existing acceptance tests cover same-actor review, superseded attempts, stale fingerprints, and omitted worker-declared commands.

Still missing:

- Dependency-aware dispatch: the feature-graph test remains an expected failure.
- Automatic, durable completion-to-child scheduling with attempt-bound receipt reconciliation.
- Required checks owned by a finalized specification, complete request-diff attribution, and explicit reviewer verdicts. Nonempty worker-supplied lists alone do not establish these guarantees.
- Read-only diagnostics for these blockers and migration behavior for the new contract fields.

The [recorded host inventory](../sprint-6-production-readiness/evidence/host-inventory.json) targets Hermes `8f897d2d23a338f7a062ebc4fa7aedc287d087de` and reports CLI startup blocked by missing `ruamel.yaml`. It is discovery evidence, not native lifecycle certification; refresh it before making new host claims.

## Scope

- Dependency-aware dispatch and reservation release for bugfix, feature, and product graphs.
- Spec-bound acceptance checks, implementation scope, and explicit reviewer verdicts.
- Public status diagnostics for queued, blocked, and contract-invalid work.
- Migration of existing schema-v6 state without fabricating receipts, approval verdicts, or verification contracts.
- Explicit no-change-needed outcomes with behavior-specific evidence and independent approval.
- Regression coverage and release evidence for the two highest-impact remaining gaps.

Out of scope: native Hermes lifecycle certification, host environment repair, provider policy changes, managed dependencies, browser adapters, broad CLI redesign, abandonment/history features, and release publication. These remain tracked in Sprint 6. Local completion of this package does not close Sprint 6's production-readiness gates.

## Exit criteria

- Both original Sprint 6 regression cases are ordinary passing tests; no expected failures or skipped checks satisfy a Sprint 7 acceptance row.
- A five-task feature and seven-task product graph can be admitted without queued tasks consuming active worker capacity.
- Implementation scope matches the request diff; checks are required by the finalized spec and cannot be weakened by submissions.
- No-change-needed outcomes require an explicit contract, behavior evidence, and independent approval.
- Reviewer evidence is bound to the current engineer attempt and an explicit approval result.
- Full local suite, compilation, diff checks, and packaging checks pass.
- All acceptance rows have reviewed evidence for the exact implementation revision. Simulation and native certification are labeled separately.

## Carry-forward boundaries

S7-01–02 implement the local portions of S6-04–05. S7-03–04 implement contract and review portions of S6-07–08. S7-05 covers the associated diagnostic portion of S6-10. These are inherited responsibilities, not prerequisites that require unfinished Sprint 6 tasks to complete first. S7-06 consolidates local evidence; native certification stays in S6-11.
