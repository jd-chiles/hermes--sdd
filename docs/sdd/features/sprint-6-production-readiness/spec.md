# Sprint 6 — production readiness

- Mode: `feature`
- Specification revision: `1`
- Created: `2026-09-28`
- Status: specified; implementation and sprint acceptance are pending.
- Baseline: `bb9381df05986f759dccd94d6a89f49a40ebb92f` (schema v5).
- Delivery boundary: verified local repository changes and a reviewable release candidate; no automatic commit, PR, release publication, deployment, or announcement.

## Objective

Make Hermes SDD dependable from installation through verified completion and subsequent requests. Prioritize execution, request lifecycle, acceptance quality, release certification, and the public command experience in that order.

## Package

- [Requirements](requirements.md): normative behavior and compatibility boundaries.
- [Architecture](architecture.md): scheduling, persistence, acceptance, and host integration design.
- [Task backlog](tasks.md): stable tasks, dependencies, ownership areas, and completion gates.
- [Acceptance matrix](acceptance-matrix.md): requirement-to-scenario traceability.
- [Verification plan](verification-plan.md): evidence collection and release gates.
- [Decision log](decision-log.md): design decisions and unresolved host contracts.
- [Sprint summary](../../../sprints/sprint-6.md): status and delivery order.

## Evidence at the baseline

The September 28 repository review ran all 53 existing tests successfully on Linux. Additional temporary-repository probes reproduced these gaps; they are not yet committed regression tests:

| Finding | Observed result | Implementation area |
| --- | --- | --- |
| Five-task feature with default worker limit | A successful fake host receives three task creations; the fourth is blocked by `max_workers` | `SDDService.sync_board` |
| Completed total runtime budget | After consuming a 10-second budget, a further 10-second reservation is admitted | `Ledger.admit_capacity` |
| Reinitialize the second request or start the third | `UNIQUE constraint failed: projects.root` | `Ledger.init_project` |
| Empty submissions and unrelated checks | Separate engineer/reviewer submissions with no files and `python -c pass` evidence can yield acceptance | `Ledger.accept_project` |

Source inspection also found that the CLI constructs a context without dispatch, unknown slash-command tokens fall through to execution, and host lifecycle receipt integration remains incomplete. The [baseline CI run](https://github.com/jd-chiles/hermes--spec-driven-development-plugin/actions/runs/36390287932) passed Linux repository checks, failed the archive-output exclusion test on macOS and Windows, and skipped all host jobs. These findings do not establish native-host behavior or certification.

## Scope

In scope:

- Dependency-aware execution, automatic receipt reconciliation, worker capacity, and cumulative runtime accounting.
- Stable request identities, repeated requests, explicit abandonment, immutable history, and schema-v5 migration.
- Versioned acceptance contracts with predefined checks, repository-diff coverage, explicit review verdicts, and justified no-change outcomes.
- Portable packaging, pinned host compatibility, extracted-artifact tests, upgrade checks, and release-candidate evidence.
- Working CLI/slash/tool surfaces, readable status, structured errors, capability diagnostics, and an accurate quickstart.

Out of scope:

- New provider routing or escalation policy, managed dependency installation, and browser automation adapters.
- A web dashboard, remote coordination service, organization policy engine, or OS sandbox.
- Automatic publication or changes to user provider credentials and existing profile configuration.

Sprint 5's unfinished native lifecycle and history work is carried into this sprint. Its existing implementation and historical verification remain baseline evidence, not proof that Sprint 6 requirements pass.

## Success measures and exit criteria

- All three workflow shapes complete under default limits without manual reservation cleanup on a certified host.
- A ten-request sequence, including restart, replays, repeated titles, close, and abandonment, preserves history and creates no duplicate native tasks.
- Consumed runtime is never refunded by completion or restart; unknown runtime cannot silently become zero.
- Missing required checks, omitted request changes, rejected review, and unsupported evidence types block acceptance.
- Every advertised platform passes the candidate artifact's install, lifecycle, recovery, and upgrade gates against recorded host revisions.
- A new user can install, complete a small change, diagnose a blocker, and recover using public documentation and commands.
- Every acceptance-matrix row has reviewed evidence. Unsupported or unverified required host behavior blocks the corresponding support claim.

## Delivery strategy

Implement the [task graph](tasks.md) as small, independently reviewable changes. Local kernel work can proceed while the host contract is investigated. Keep execution disabled for capabilities that cannot be verified; do not substitute mock evidence for native certification. Release preparation produces a candidate and a go/no-go report; publishing it is outside this sprint's execution authorization.
