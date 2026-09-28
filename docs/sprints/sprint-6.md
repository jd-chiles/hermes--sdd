# Sprint 6 — production readiness

Status: active, 2026-09-28. Local identity, migration, runtime-accounting, and packaging slices are implemented; scheduler, acceptance-contract, public-interface, and native-host certification remain open.

## Objective

Make installation, execution, acceptance, recovery, and repeated requests dependable. This sprint follows the repository review at `bb9381df05986f759dccd94d6a89f49a40ebb92f` and carries forward Sprint 5's unfinished native lifecycle and history work.

## Development package

- [Specification and baseline findings](../sdd/features/sprint-6-production-readiness/spec.md)
- [Requirements](../sdd/features/sprint-6-production-readiness/requirements.md)
- [Architecture](../sdd/features/sprint-6-production-readiness/architecture.md)
- [Stable task backlog](../sdd/features/sprint-6-production-readiness/tasks.md)
- [Acceptance matrix](../sdd/features/sprint-6-production-readiness/acceptance-matrix.md)
- [Verification plan](../sdd/features/sprint-6-production-readiness/verification-plan.md)
- [Decision log](../sdd/features/sprint-6-production-readiness/decision-log.md)

## Priorities

| Order | Outcome | Task IDs | Status |
| --- | --- | --- | --- |
| 1 | Complete dependency-aware execution and cumulative resource accounting | S6-01–02, S6-04–05 | Open |
| 2 | Reliable repeated requests, abandonment, migration, and history | S6-03, S6-06 | Open |
| 3 | Spec-bound verification, actual diff coverage, explicit review | S6-07–08 | Open |
| 4 | Portable candidate artifacts and pinned-host certification | S6-09, S6-11 | Open |
| 5 | Consistent commands, diagnostics, and tested onboarding | S6-10, S6-12 | Open |

Task dependencies, rather than this priority summary alone, determine execution order. Host discovery and failing regressions come first; identity/migration precedes the dependent scheduler and lifecycle changes.

## Exit criteria

- Every requirement has passing evidence in the acceptance matrix.
- Default workflows complete without manual capacity cleanup.
- Repeated requests and restarts preserve immutable history.
- Acceptance cannot omit required checks, request changes, or independent approval.
- The exact candidate passes supported-platform install, lifecycle, recovery, and upgrade checks.
- The public quickstart works in a fresh home with actionable diagnostics.
- Independent review approves a release-candidate go/no-go report. Publishing is outside scope.

## Current evidence

The baseline review ran 53 tests successfully on Linux and reproduced additional execution, budget, lifecycle, and acceptance defects. Sprint work now runs 72 tests, including 5 migration tests and 2 explicit expected-failure tests for the remaining scheduler and acceptance-contract gaps. Packaging regressions pass locally. Host inventory targets Hermes `8f897d2d23a338f7a062ebc4fa7aedc287d087de`; the installed CLI is blocked by a missing `ruamel.yaml` dependency, so native lifecycle support remains unverified.
