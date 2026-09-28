# Sprint 7 requirements

Revision 2. Requirements below describe the target behavior. Existing nonempty-submission guards are partial evidence only; full acceptance remains pending.

### FR-01 — Reserve only runnable work

Persist the full directed acyclic task graph and validate unknown parents/cycles before any dispatch. Reserve worker/runtime capacity only for tasks whose parents have current successful completion receipts and whose request is active and unpaused. Queued tasks remain visible without consuming capacity. Check worker limits, cumulative runtime, file ownership, and dispatch intent atomically before launch. A scheduler pass is idempotent and may be rerun after restart. Native card creation must be deferred unless the host proves it cannot launch unadmitted work.

### FR-02 — Release and promote deterministically

A validated terminal receipt releases only the matching attempt's reservation and records its actual runtime. Successful completion makes eligible children schedulable; failed or interrupted completion does not. Ambiguous outcomes retain conservative capacity until reconciliation. Bind receipts to request, task, dispatch operation, and native attempt identity. Duplicate receipts have no new effect; conflicting replays are rejected; late receipts cannot regress state or release a later attempt's capacity. Persist the scheduling wake-up with completion so restart cannot lose child eligibility. Retry/promotion uses the same admission rules as initial execution.

### FR-03 — Require implementation scope

For an `implemented` outcome, engineer submissions must collectively cover the request-owned diff and contain actual implementation changes. Capture baseline Git revision, tracked changes, and relevant untracked files before request work. Detect additions, modifications, deletions, and renames relative to that baseline; preserve unrelated pre-existing work. Exclude runtime/generated bookkeeping by explicit policy, never by worker-provided exclusions. Missing baseline, omitted files, stale content, ambiguous attribution, or an unsupported repository adapter blocks acceptance. Initially support Git repositories; do not imply that a nonempty arbitrary file list proves implementation.

An explicit `no_change_needed` contract permits an empty implementation diff only with a rationale, required behavior-specific checks proving the requested behavior already holds, and independent approval. Report this outcome distinctly. A generic successful no-op command cannot substitute for a required check in either outcome.

### FR-04 — Bind required checks to the spec

Finalize the criterion-to-check contract before admitting implementation work. Requirements/architecture tasks may refine a draft without pretending implementation is ready. Persist criterion IDs, check IDs, evidence types, exact commands/scenarios, expected results, and applicable scope in the spec revision. Every required criterion must have a supported verification path. Workers may add checks but cannot remove or replace the spec's required checks through a submission.

Each required check needs current evidence bound to its check ID, criterion, spec revision, implementation attempt set, and content fingerprint. A failed check cannot be hidden by unrelated successes. Contract changes require an explicit revision and invalidate affected submissions/evidence/reviews; do not silently reinterpret older results. Unsupported evidence types block with a concrete remedy.

### FR-05 — Require explicit review approval

Reviewer submissions carry an explicit verdict (`approve` or `request_changes`). Only an independent `approve` verdict for the current engineer attempt can satisfy review. A summary that merely exists is not an approval.

Bind approval to the current spec revision, engineer attempt set, and entire request diff. A current request-changes verdict blocks acceptance even when automated checks pass. Require findings or a rationale with the verdict. Legacy reviews lacking a verdict require resubmission; never infer approval from prose or an old task status.

### FR-06 — Explain blockers without changing work

Status and doctor expose task dependencies, runnable/queued state, active reservations, reconciliation needs, contract revision/state, missing check IDs, and review blockers. Each blocker identifies the affected request/task, a stable code, and an actionable next step. JSON and human views must describe the same state. Reading diagnostics must not create a request, dispatch work, reserve/release capacity, revise a contract, or rewrite archived outcomes. Existing unrelated CLI behavior is outside this sprint.

### NFR-01 — Preserve durable truth

SQLite remains authoritative. Reservation, receipt, promotion, and acceptance decisions are transactional and idempotent. JSONL is rebuilt from committed events.

Bind operation keys to payloads and reject changed-input replay before mutation. Concurrent coordinators must have one admission winner; use leases consistently across initial dispatch, recovery, and promotion. Closed/abandoned requests cannot be changed by scheduler, receipt, contract, or review APIs. Receipt ingestion and the durable scheduling wake-up commit together; external dispatch happens after intent commit.

### NFR-02 — Host boundary honesty

Local scheduler simulations must be reported separately from native host evidence. Unsupported host lifecycle behavior remains blocked and cannot be inferred from local mocks.

### NFR-03 — Upgrade without inventing evidence

Migrate populated schema-v6 ledgers transactionally with a recoverable backup; retain schema-v5 upgrade regression coverage. Preserve IDs, attempts, history, native references, and resource counters. Records missing required receipt, baseline, contract, or verdict fields receive explicit reconciliation/resubmission blockers. Never promote an old submission into a new approval automatically. Repeated migration is idempotent; failure leaves prior data recoverable and dispatches nothing. Reject future schemas before mutation.

### NFR-04 — Bound work and preserve permissions

Bound each scheduler pass, receipt batch, external call, and diagnostic output. Persist progress so a bounded pass can resume. Retain host permission boundaries and the distinction between ownership coordination and OS isolation. Preserve user changes and existing profiles; credentials must not enter ledger events or verification reports.
