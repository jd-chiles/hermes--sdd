# Sprint 3 — trustworthy acceptance and recoverable execution

Status: active, 2026-09-27. First implementation batch validated locally; routing/escalation integration and host release gates remain open.

## Objective

Make accepted status trustworthy for the current submission and make interrupted execution recover without dropping dependencies or duplicating work. Keep release artifacts reproducible. Make low/med/high task difficulty drive verified authorized routing, with failure-aware escalation that preserves finite native attempts.

Inputs: [project review](../reviews/sprint-3-review.md), [Sprint 2](sprint-2.md), and [release gates](../release-checklist.md). Sprint 2's WSL2 closure remains an external verification carryover; it does not block local Sprint 3 development.

## Ordered backlog

| ID | Priority / size | Deliverable and acceptance criteria | Depends on | Status |
| --- | --- | --- | --- | --- |
| S3-01 | P2 / S | Reproducible source archive: repeated builds have identical hashes despite clock, destination name, or source metadata changes; previous output/manifest and local workspace files are excluded; source symlinks are rejected. | — | Implemented; 4 regression tests pass; host validation pending |
| S3-07 | P1 / M | Per-task low/med/high assessment independent of workflow and role; persist dimensions, rationale, policy version, and overrides. Verify tier-to-effective-route mappings and report shared-route/unsupported routing explicitly. See the [routing contract](../design/task-tiers-and-escalation.md). | — | In progress: assessment persisted in plans/status; source routing contract passes; effective routing pending |
| S3-08 | P1 / L | Implement failure taxonomy, authorized route selection, provider cooldown/circuit breaker, and durable idempotent escalation. Separate repair/provider counters; discover Hermes native attempt semantics and honor its cap where supported, otherwise enforce a durable plugin launch cap. A preventative fixture adapted from OpenCode task 240 makes zero retry calls until a qualifying recovery change, including across restarts; pinned-host tests prove route application. | S3-07, S3-03, S3-04 | Specified; implementation pending |
| S3-02 | P1 / L | Unify acceptance rules around latest per-task attempts and current spec revision. Require distinct engineer/reviewer actors and review tied to the current implementation. Check all declared required commands with deterministic evidence ordering and matching attempt file scope. New submissions and failed reevaluations invalidate accepted status. Tests cover stale retries, same-actor review, missing/failed checks, mismatched scope, and status invalidation. | — | Implemented locally; acceptance regressions pass |
| S3-03 | P1 / M | Parse documented terminal response envelopes explicitly; fail visibly on malformed/failed host responses. Match exact stable-task markers. Never dispatch a child without all required native parents. Product implementation waits for both UX and architecture. Recovery tests cover interruption after native creation, duplicate matches, and missing parents. | — | In progress: exact recovery matching, JSON envelopes, missing-parent stop, and product dependencies tested; provisioning and dispatch idempotency still open |
| S3-04 | P1 / M | Acquire leases and ownership with atomic transactional admission; deduplicate before mutation. Define conflict behavior for operation-ID reuse. Concurrent-connection tests prove one winner and unchanged state on rejected retries. Define SQLite as source of truth and rebuild JSONL after interrupted export. | — | In progress: atomic ownership/lease admission and replay checks tested; JSONL rebuild implemented; lease renewal and dispatch coordination still open |
| S3-05 | P2 / M | Exercise slash/CLI plan, build, fix, pause, resume, and fresh recovery. Fix executes consistently with its description; absent dispatch is explicit; pause gates new work. Document verified command limits. | S3-03 | In progress: fix dispatch intent, fresh recovery, pause admission, CLI default, and absent dispatch tested; host CLI integration pending |
| S3-06 | P2 / M | Pin a supported Hermes baseline, run extracted-artifact validation in host CI, and automate clean install/profile-preservation checks against a suitable immutable plugin revision. Confirm Sprint 2 WSL2 result and align release documentation. | S3-01, host access | Queued |

Sizes are relative estimates, not calendar commitments. Prioritize the S3-07 host routing capability check alongside S3-02, then S3-03 and S3-04, then integrate S3-08. Defer S3-05/06 implementation if needed before compromising P1 acceptance criteria; host verification remains a release gate. S3-07 is partially implemented; S3-08 remains pending and must not be represented as active automatic escalation. No additional agents or native workers were launched for this kickoff.

## Kickoff delivered

- Reviewed implementation and recorded prioritized, source-specific findings and two acceptance reproductions.
- Added four regression tests, observed all four fail against baseline, then implemented the archive fix.
- Builder now uses explicit source roots, excludes its own output and manifest, normalizes tar metadata and gzip headers, emits portable member paths, and rejects source symlinks.
- Local validation: 9 tests pass; Python compilation passes.
- Host smoke remains unverified: installed Hermes cannot prepare its runtime on this session's read-only installation filesystem. GitHub API was unreachable when checking Sprint 2 CI.

## Exit criteria

- S3-02/03/04 regressions pass alongside the existing happy path and packaging tests.
- S3-05 command behavior is tested and documented; any deferred behavior is explicitly scoped out.
- Linux, macOS, and WSL2 repository checks pass; pinned-host artifact checks and profile-preservation evidence are attached before release.
- Acceptance cannot reuse superseded evidence or self-review; a partial native dispatch cannot launch a dependent task early.
- S3-07/08 pass the tier, failure-classification, effective-route, durable-budget, and regression matrix adapted from OpenCode task 240. Hermes host capabilities are verified independently of OpenCode. Shared routes never masquerade as escalation; provider failures never trigger blind retries.
- No unresolved P1 findings from this review; deferred lifecycle features are tracked without claiming support.

## Deferred follow-up

Enforce broader worker concurrency limits (repair/provider/native-attempt and total runtime/cost admission are now part of S3-08); support closing a completed request and starting another without ledger deletion; integrate host lifecycle callbacks; add managed dependency and browser adapters. These need their own scoped acceptance contracts after the current correctness work.

## Implementation batch 1

- S3-02: schema v2 adds immutable submission context. Acceptance uses current attempts, current spec revision, distinct reviewer actors, reviewed engineer file coverage, declared command results, and deterministic evidence order. New submissions and failed reevaluation invalidate accepted state. Verification checks attempt/scope before running and rejects checks that mutate submitted files. Old attempts without context require resubmission; no acceptance is inferred during migration.
- S3-03/04: native JSON envelopes are decoded and nonzero/in-progress responses fail closed; exact markers and duplicate detection replace substring recovery. Missing parent receipts stop child creation. Product implementation depends on UX and architecture. Ownership/lease admission uses immediate SQLite write transactions; changed operation-ID payloads are rejected before mutation; export can rebuild JSONL from SQLite.
- S3-07: per-task dimensions and rationale are saved with the specification and shown in status/spec artifacts. Unknown dimensions default to med; the highest risk wins. Low requires every dimension to be assessed low. Policy changes cannot silently replace the saved specification. Status explicitly reports effective routing as unverified.
- Hermes source contract passed at `8f897d2d23a338f7a062ebc4fa7aedc287d087de`: Kanban supports `--model`, `--provider`, and native idempotency keys; its actual worker argv builder forwards model/provider overrides. `--max-retries` is a consecutive-failure breaker, not a lifetime launch cap. Run `python3 scripts/host_routing_contract.py --host-root <hermes-checkout>` to reproduce. This test launches no workers and does not validate provider authorization or effective runtime routes.
- Validation: 35 local tests pass and Python compilation passes. Full installed-host smoke remains blocked by the runtime installation filesystem as recorded above; remote platform CI has not been rerun.

Next: implement authorized route configuration and effective-route receipts, then the durable escalation/budget state machine. Complete native provisioning/error handling, use native idempotency keys across dispatch interruptions, and renew/reconcile dispatch leases before closing S3-03/04. Do not auto-unblock a failed provider task as a substitute for those missing gates.
