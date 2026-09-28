# Sprint 6 requirements

Revision 1. All requirements below are proposed implementation requirements; none is marked complete by creating this package.

## Execution and resource accounting

### FR-01 — Separate queued tasks from active workers

Persist the complete dependency graph without consuming worker slots for tasks that cannot run. Reserve capacity atomically before a task can become runnable, including retries and promotions. Dependency completion must schedule newly eligible tasks automatically. The default limit of three must permit three-, five-, and seven-task workflows to complete. Board creation must not accidentally launch work before admission.

### FR-02 — Reconcile native lifecycle receipts

Use verified host callbacks or bounded polling to reconcile start, success, failure, interruption, and review transitions. Receipts must identify the request, task, native attempt, and operation. Duplicate or out-of-order receipts must not duplicate launches, regress terminal state, or release another attempt's capacity. Persist dispatch intent before external mutation; ambiguous outcomes retain capacity and block redispatch until reconciled. Pause must distinguish a requested interruption from a confirmed stop.

### FR-03 — Enforce runtime budgets across the request

Admission must compare completed actual runtime plus active runtime commitments plus the proposed commitment against the total cap. Track cumulative per-task runtime across attempts separately from repair-count budgets. Account for actual runtime exceeding estimates, including failed and interrupted attempts. Restart and completion must not reset consumption. Unknown elapsed time requires conservative accounting and a visible blocker. Enforcing a hard running deadline requires verified host interruption/deadline support; otherwise report that capability as unsupported and do not claim a hard cap.

## Request lifecycle

### FR-04 — Resolve the active request by repository association

Assign each request a permanent unique ID and maintain at most one active request per canonical repository root. Repeating initialization of the same active request returns that identity without changing its stage, spec, or limits. Different inputs require an explicit revision or termination of the active request. Request IDs must namespace native identities and artifact locations so repeated titles cannot reuse old cards or overwrite old specifications.

### FR-05 — Preserve terminal history and support abandonment

Close requires current acceptance, no active or ambiguous workers, and an unpaused request. Revalidate acceptance before closure. Add explicit abandonment for unfinished requests: stop new admission, reconcile or confirm worker interruption, then mark the request abandoned without labeling it accepted. Closed and abandoned requests are immutable through public mutation APIs; repeating the same terminal operation is idempotent. Provide read-only history and selected-request diagnostics. Neither pause, resume, recover, nor accept may reopen terminal requests.

## Acceptance contract

### FR-06 — Define required verification before implementation

The versioned spec must map each required criterion to explicit required checks/evidence types and the expected success condition. Finalize that contract before implementation is admitted; requirements/architecture work may refine a draft. Workers may add checks but cannot remove, replace, or weaken required checks in their submissions. An explicit spec revision invalidates affected evidence and review. Unsupported required evidence types block acceptance with a remedy.

### FR-07 — Cover the actual request changes

Record the starting repository revision and pre-existing tracked/untracked changes. Reconcile submissions with the request-owned diff, including additions, modifications, deletions, renames, and relevant untracked files. Reject omitted changes and stale content. Preserve pre-existing user changes and do not silently attribute them to the worker. Exclude plugin runtime/generated bookkeeping by explicit policy. Ambiguous ownership or an unsupported repository type blocks acceptance rather than guessing.

### FR-08 — Require a review verdict and distinguish no-change results

Reviewer results must explicitly approve or request changes, use an actor independent of the implementation actor, and bind to the current spec, engineer attempts, and complete request diff. A request-changes verdict blocks acceptance. A no-change-needed outcome requires an explicit rationale, evidence that the requested behavior already holds, and independent approval; it is reported separately from an implemented change. Empty file lists or unrelated successful commands alone cannot satisfy an implementation request. Automated check success does not establish semantic correctness without this review.

## Release certification

### FR-09 — Build portable, reproducible artifacts

Normalize source/output identity consistently across supported platforms; exclude the archive and manifest even through equivalent parent paths. Preserve the source-symlink rejection policy. Repeated builds from the same inputs produce the same bytes and checksum, regardless of output location or filesystem timestamps. Validate the packaged manifest, registered tools, and declared version for consistency.

### FR-10 — Certify pinned hosts using the candidate artifact

Record the exact plugin revision, artifact digest, Python version, host revision, and OS for each certification. Test clean installation, profile preservation, command execution, completion, interruption/recovery, and schema-v5 upgrade using the extracted candidate artifact in an isolated home. CI must run pinned-host checks for the supported platform independently of unrelated platform job failures; release readiness still requires all advertised targets to pass. Prepare version/changelog/checksum/compatibility metadata without publishing automatically.

## Public experience

### FR-11 — Make public command surfaces consistent

CLI, slash commands, and tools must call the same service behavior, with execution using a verified host dispatch boundary. Keep JSON available for tools and CLI `--json`; default human output identifies request, stage, progress, blocker, and exact next action. Define nonzero CLI exit codes for operational errors and acceptance failure. Handle invalid arguments without tracebacks. `/sdd help` must be explicit; unknown command-like inputs must not silently launch work. Preserve free-form requests through a documented unambiguous form. Update the tool manifest and help from the supported operation registry or validate their parity.

### FR-12 — Make onboarding and diagnostics actionable

Provide an exact tested install example using the canonical repository and an immutable candidate/release reference, prerequisites, a supported-host matrix, gateway restart guidance where required, an example workflow, and recovery/uninstall instructions. Doctor must report verified, unsupported, or unverified capabilities with evidence and remedies, including CLI dispatch, receipts, interruption, routing, and schema compatibility. Diagnostics must not create a request, launch a worker, or modify existing profile configuration. Retain the installed plugin identifier unless a migration is supplied.

## Non-functional and compatibility requirements

### NFR-01 — Durable, atomic state

Use SQLite as authoritative state and JSONL as a rebuildable export. State transitions, accounting, and their event records must commit atomically. Bind idempotency keys to inputs; changed-payload replay is rejected before mutation. All launch paths use the same lease/admission protocol, and overlapping file ownership remains serialized.

### NFR-02 — Safe schema-v5 migration

Provide a recoverable backup and transactional migration before dispatch. Preserve request IDs, attempts, evidence, ownership, native references, and counters. Resolve the existing synthetic archived-root representation without rewriting historical evidence. Do not invent acceptance contracts or receipt evidence for legacy attempts; expose an upgrade-required blocker where new evidence is needed. Unsupported future schemas must be rejected before mutation. Migration is idempotent; failed migration leaves the prior ledger recoverable and launches nothing.

### NFR-03 — Bounded and private operation

Bound host calls, polling, verification duration, and captured output; preserve necessary evidence without leaking credentials or sensitive environment values in diagnostics/release logs. Use host-supported execution and permission boundaries where applicable. Ownership metadata remains coordination, not an OS sandbox. Existing user work and profiles must survive install, run, upgrade, and uninstall.
