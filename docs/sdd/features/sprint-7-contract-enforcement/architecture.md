# Sprint 7 architecture

Revision 2. This is a target design; new interfaces and record names below are proposals until implemented and verified.

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| `planning.py` | Validate the complete task graph; render versioned criteria/check contracts |
| `core.py` | Authoritative admission, receipts, dependency eligibility, baselines, contracts, verdicts, migration, and acceptance |
| `bridge.py` | Normalize supported host responses; distinguish verified receipts from ambiguous outcomes |
| `__init__.py` | Coordinate bounded scheduler passes and expose validated operations/diagnostics |
| `tests/` | Deterministic host simulator, real Git fixtures, migration, concurrency, and acceptance scenarios |

Hermes owns worker processes and its board persistence. The plugin never writes Hermes databases. A successful simulated receipt is evidence about the local reducer only.

## Scheduling model

```text
queued -- all parents successful + admission --> dispatch_pending
dispatch_pending -- validated launch receipt --> running
dispatch_pending -- ambiguous response -------> reconciling
running -- validated success ----------------> completed
running -- validated failure/interruption ---> blocked
reconciling -- authoritative receipt --------> running/completed/blocked
```

These are logical states; map them explicitly to existing stored task statuses during implementation. Task completion is not project acceptance. Review and QA tasks may complete operationally while project acceptance still fails its contract.

A bounded scheduler pass acquires the request lease, checks terminal/paused state, reconciles unresolved operations, and evaluates parents from the stored graph and current receipts. Within a transaction, an eligible task reserves resources and records an immutable payload-bound dispatch intent/event. Perform the external operation after commit, then persist the validated launch receipt. A queued child consumes no reservation. Native card creation is deferred unless a certified host contract proves the created card cannot run before admission.

For a product graph, both UX and architecture must complete before implementation becomes eligible. Missing parents or cycles block before any native mutation. Capacity exhaustion leaves eligible work queued with a visible capacity reason rather than failing graph creation. Initial launch, recovery, and promotion share the same admission path.

## Receipt reducer and durable wake-up

Normalize terminal receipts into request ID, task ID, dispatch operation ID, native attempt ID, outcome, elapsed runtime, and receipt identity. Identity must come from a verified bridge adapter; worker prose is insufficient. One transaction validates the receipt, stores it, records runtime, releases the matching reservation/ownership where appropriate, updates task state, and records a scheduler wake-up.

Replaying the same receipt returns its prior result. Reusing a receipt identity with different inputs fails. A receipt for an old attempt cannot alter a newer attempt. Ambiguous duration/state retains the existing commitment and a reconciliation blocker. Actual consumed runtime is never refunded by restart or completion.

The service drains persisted wake-ups in a bounded pass after ingestion and on recovery/resume. A crash after receipt commit but before child dispatch therefore loses no work. Native callbacks or polling that invoke ingestion remain a separate host integration gate; this sprint proves the local API and reducer with a deterministic simulator.

## Verification contract and scope

Conceptual contract fields:

| Record | Required content |
| --- | --- |
| Contract revision | Request ID, spec revision, draft/finalized state, outcome (`implemented` or `no_change_needed`) |
| Criterion/check mapping | Stable criterion/check IDs, supported evidence type, command/scenario, expected result, scope |
| Repository baseline | HEAD identity and tracked/untracked content snapshot with explicit bookkeeping exclusions |
| Submission | Engineer attempt, spec revision, changed files, additional checks, summary |
| Review | Explicit verdict, actor, rationale/findings, spec revision, engineer attempt set, diff fingerprint |
| Evidence | Check/criterion IDs, implementation binding, executed command/scenario, result, content fingerprint |

Required checks are authored during planning and finalized before engineer admission. Additional worker checks supplement that contract. Use an explicit revision operation to change requirements; retain old records and invalidate affected results instead of modifying immutable evidence.

Compare request-owned changes against the captured Git baseline, including deleted/renamed files and relevant untracked additions. Pre-existing dirty files are preserved and distinguished from request changes. If attribution cannot be established, require explicit reconciliation rather than silently crediting unrelated changes. A missing or unsupported baseline blocks scope certification.

Acceptance reads the finalized contract, current attempts, current repository diff, required check evidence, and explicit independent review in a consistent evaluation. Every required check must pass against the current implementation; every request change must be covered by submissions and review. An explicit no-change-needed outcome still needs required behavior evidence and independent approval. Neither an empty diff nor a command's zero exit status is sufficient by itself.

## Persistence and migration

Add or extend records for dependency edges, normalized receipts, scheduling wake-ups, contracts/checks, baselines, and review verdicts. Physical tables and the next schema version are selected during implementation, not assumed by this draft. Retain schema-v6 request associations and accounting semantics.

Before altering populated state, create a recoverable backup and apply schema/data/version updates transactionally. Legacy single-parent fields are insufficient for the product join; use the stored `parent_keys` graph where available and reject inconsistent mappings. Preserve existing native task IDs and attempts. Missing receipt identity, diff baseline, finalized checks, or approval verdict produces an upgrade blocker; do not synthesize successful evidence from old statuses.

Provide operator restore instructions with the implementation: stop coordinators, preserve the failed ledger and sidecar files, restore the consistent SQLite backup through a tested procedure, and validate it before enabling execution. Do not prescribe deleting live WAL files. Test mid-migration failure and future-schema refusal.

## Public interfaces and diagnostics

Expose validated service operations for contract finalization/revision, explicit review submission, and receipt ingestion. Extend tool schemas/help consistently and test their registration. Receipt ingestion is a host-adapter operation; ordinary user text must not impersonate native authority.

A read-only diagnostic evaluator provides stable blocker codes such as `waiting_for_parent`, `capacity_exhausted`, `receipt_unresolved`, `contract_unfinalized`, `required_check_missing`, `scope_unverified`, and `review_changes_requested`, with task/check IDs and remedies. Human formatting and JSON consume the same result. Doctor reports host capability evidence as verified, unsupported, or unverified; it does not dispatch or initialize a request.

## Failure boundaries

- SQLite commit failure: external dispatch has not yet occurred for a new intent.
- Dispatch timeout: retain intent/reservation; reconcile before retry.
- Receipt commit succeeded, wake-up not processed: replay persisted wake-up after restart.
- Spec/implementation changed: reject stale evidence and approval, preserving history.
- Migration or host capability ambiguous: block the affected operation with actionable diagnostics.

The [acceptance matrix](acceptance-matrix.md) assigns evidence to these boundaries. Local conformance does not enable unverified native lifecycle operations.
