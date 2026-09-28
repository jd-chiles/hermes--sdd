# Sprint 6 architecture

This is the target design, not a description of already implemented behavior. Physical table layouts and native API details must be settled against the pinned host during S6-01; the invariants below are mandatory.

## Boundaries

- `planning.py`: draft plan, stable graph, and versioned criterion/check contract.
- `core.py`: transactional request state, identities, ownership, attempts, evidence, accounting, and migration.
- `bridge.py`: capability probes and normalized native receipts through supported Hermes interfaces.
- `__init__.py`: service orchestration and shared tool/CLI/slash operation registry.
- `scripts/` and CI: artifact construction, isolated host certification, and release evidence.

Keep host databases private to Hermes. Host operation receipts must be decoded and validated before local state claims that an external action succeeded.

## Request identity and lifecycle

Introduce a repository-to-active-request association separate from immutable request identity. Create and update that association in a transaction with a uniqueness constraint. Query the active association during initialization; never recompute the original request's ID as the lookup strategy.

New boards, stable task markers, dispatch keys, and spec directories include request identity. Preserve existing artifact paths as historical references during migration; a repeated title gets a distinct directory and board identity.

| Operation | Preconditions | Result |
| --- | --- | --- |
| Plan | No active request, or identical replay | New planned request, or unchanged existing result |
| Execute | Active request; verified required capabilities; finalized implementation contract before engineer launch | Admit eligible work |
| Pause | Nonterminal request | Stop admission immediately; request interruption where supported; show pending receipts |
| Resume/recover | Nonterminal request; host state reconcilable | Reconcile before admitting eligible work |
| Accept | Current criteria, evidence, diff, and independent approval | Accepted result or actionable review blockers |
| Close | Current acceptance revalidated; unpaused; no active/ambiguous work | Immutable closed request; clear active association |
| Abandon | Explicit command; no active/ambiguous work after reconciliation | Immutable abandoned request; clear active association |
| History | Any request | Read-only request/evidence summary |

Terminal records are rejected by every mutator, including APIs accepting a historical task ID. Replays of the matching terminal operation return the recorded result. Concurrent initialize/close operations cannot create two active requests. A repository move requires an explicit association migration; do not infer it by silently reusing a root hash.

## Scheduling and native reconciliation

Persist the entire graph locally. Native task creation is safe before execution admission only if the host can prove the task remains non-runnable. Otherwise defer native creation until dependency and resource admission pass. A queued dependent task does not hold a worker reservation.

For each eligible launch:

1. Acquire/renew the project lease and reconcile outstanding operations.
2. In one transaction, validate request state and parents, reserve worker/runtime capacity, and persist a payload-bound dispatch intent and event.
3. Dispatch with the stable native idempotency key through the verified host boundary.
4. Validate the receipt and persist its native task/attempt identity.
5. On timeout or ambiguous response, retain the reservation and mark reconciliation required; never blindly recreate the task.

A callback or bounded poller ingests receipts through one idempotent reducer. A terminal receipt commits elapsed runtime, releases the matching reservation and ownership as appropriate, records the event, and makes eligible children schedulable. The next scheduler pass does not require user cleanup. Late receipts for previous attempts cannot release current capacity. Recovery promotion uses this same protocol and the existing repair/provider counters.

Capability records contain host revision, capability name, verification result, evidence reference, and timestamp. Invalidate them when the host revision changes. If native creation auto-starts tasks and there is no safe launch/dependency boundary, execution is unsupported on that host.

## Runtime accounting

For admission, evaluate:

```text
total exposure = completed actual seconds
               + sum(active commitments)
               + proposed commitment

task exposure  = actual seconds from prior attempts of this task
               + active commitments for this task
               + proposed commitment
```

Compare each exposure with its configured cap within the admission transaction. An active commitment must conservatively cover its permitted remaining execution, not merely an optimistic estimate. Trusted elapsed receipts update exposure; an overrun becomes recorded usage and blocks further work, never negative capacity. For an unknown receipt retain the outstanding commitment and a blocker until reconciliation establishes actual usage.

Where the host supports an enforceable deadline, pass the remaining authorized runtime and verify interruption semantics. Without that support, expose accounting/admission limits separately from hard runtime enforcement and block any workflow requiring the latter. Define total runtime as cumulative worker-seconds; parallel workers each consume time. Report wall-clock duration separately.

## Acceptance and change attribution

Persist criterion-to-check mappings in each spec revision. A check identifies its evidence type, command/scenario, expected result, and applicable scope. Draft requirements can change before implementation; finalized contracts require explicit revision, with affected submissions/reviews invalidated.

Capture baseline HEAD plus tracked and untracked working-tree state before generated artifacts are written. Compute the request diff relative to that snapshot without discarding pre-existing changes. Match submitted files and reviewer scope to that diff, including deletions and renames. Plugin runtime and generated spec artifacts have explicit exclusions; excluded paths must not conceal product changes. For non-Git repositories, report unsupported diff certification until an equivalent tested snapshot adapter exists.

Acceptance requires current required evidence, complete diff coverage, current engineer submissions, and an independent explicit approval verdict. Store the outcome as `implemented` or `no_change_needed`; the latter requires behavior-specific evidence and justification. Passing process exit status alone cannot prove a natural-language criterion. No-op check execution cannot replace a required behavior check. Close reuses the same acceptance evaluation and cannot trust only a cached stage.

## Migration and audit

Use an explicit schema migration with backup/restore instructions. Preserve old project IDs and artifact/native references; create active associations from canonical roots and archive metadata from synthetic roots. Stop on ambiguous mappings. Preserve immutable attempts/evidence and mark legacy contracts unverified rather than rewriting them as compliant.

Use transactionally recorded events (or an outbox committed with state) for lifecycle changes. JSONL exports follow committed state and are rebuildable after interruption. Validate schema compatibility before DDL or other mutation. Exercise migration on populated, active, closed, and malformed/ambiguous fixtures.

## Commands and release boundary

A shared operation registry defines validation, service dispatch, tool schemas, manifest entries, and help. CLI execution obtains a supported host adapter; missing dispatch is a structured failure with nonzero exit status. Human formatting wraps the same result envelope exposed by `--json`. Add history, abandon, and help consistently without changing the installed plugin ID casually.

Build the candidate once and certify its digest from an isolated extracted directory/home. Pinned-host certification and platform repository checks have independent scheduling, while the final release gate aggregates all required results. Store exact versions, commands, sanitized receipts, checksums, and compatibility limitations in the candidate report. Publication is a separate action.
