# Sprint 7 acceptance matrix

Revision 2. Existing AC-01–08 IDs are retained. All rows await Sprint 7 acceptance review; existing guards/tests are partial baseline evidence, not completion of expanded scenarios. `Local` means deterministic integration evidence; no row here certifies a native host.

| ID | Requirements | Scenario | Expected result | Evidence / task |
| --- | --- | --- | --- | --- |
| AC-01 | FR-01, FR-02 | Bugfix (3 tasks) and feature (5 tasks), default limits | Full graph persists; only runnable work reserves slots; complete flows finish through receipt-driven scheduling without manual capacity cleanup | Local simulated host + ledger/event assertions; S7-01–02 |
| AC-02 | FR-01, FR-02 | Product (7 tasks), UX/architecture complete in either order | Implementation waits for both current parent receipts, then starts once; product flow completes | Local join/restart scenarios; S7-01–02 |
| AC-03 | FR-02, NFR-01 | Duplicate or conflicting receipt; old receipt after a newer attempt | Identical replay has no new effect; changed-payload replay rejected; no late release or duplicate dispatch | Local receipt and event assertions; S7-02 |
| AC-04 | FR-03, FR-04 | Empty scope plus unrelated no-op evidence for an implemented request | Reject with scope/contract blocker; nonempty unrelated files also fail request-diff coverage | Real Git fixture + acceptance integration; S7-03 |
| AC-05 | FR-04 | Worker omits/replaces required spec check or executes unrelated successful check | Required check remains mandatory and named in blocker; only matching current evidence satisfies it | Local finalized-contract integration; S7-03 |
| AC-06 | FR-05 | Independent reviewer requests changes or omits verdict | Reject even with passing checks; no approval inferred from summary or task status | Local review integration; S7-04 |
| AC-07 | FR-05 | Same actor reviews, or approval targets old spec/engineer attempts/diff | Reject; current independent explicit approval succeeds only with other gates met | Local review/fingerprint integration; S7-04 |
| AC-08 | FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, NFR-01, NFR-02, NFR-03, NFR-04 | Aggregate sprint exit review | Every row has evidence; original regression cases ordinary passes; compilation/diff/package gates pass; native limits explicit | Full verification report and independent review; S7-06 |
| AC-09 | FR-01 | Unknown dependency or cycle | Graph rejected before reservation, dispatch, or partial external creation | Local invalid-graph fixture + zero-call assertion; S7-01 |
| AC-10 | FR-01, NFR-01 | Two coordinators at cap; pause/close racing admission; restart after intent | One admission winner; no terminal/paused launch or overlapping ownership; unresolved intent reconciled before retry | Local concurrency/fault injection; S7-01 |
| AC-11 | FR-02, NFR-01 | Crash after receipt commit before child scheduling | Durable wake-up survives restart; eligible child launches once and only its reservation is charged | Local restart/event assertions; S7-02 |
| AC-12 | FR-02, NFR-04 | Failed/interrupted parent, ambiguous duration, overrun, recovery promotion | Children remain blocked; unknown capacity retained; actual consumption preserved; retries obey all admission gates | Local reducer/runtime integration; S7-02 |
| AC-13 | FR-03 | Dirty baseline plus added/deleted/renamed/untracked request changes; missing baseline/non-Git root | Complete request changes required; user changes preserved; ambiguous or unsupported attribution blocks | Real temporary Git repositories + unsupported-root fixture; S7-03 |
| AC-14 | FR-03, FR-04 | Unfinalized contract, revised contract, unsupported evidence, valid no-change-needed outcome | Engineer admission waits for finalization; revisions invalidate affected evidence; unsupported checks block; justified no-change outcome reported distinctly | Local contract/admission/acceptance integration; S7-03 |
| AC-15 | NFR-03 | Populated schema v6 upgrade, v5 regression, repeat/failing migration, future schema | Backup recoverable; identity/history/accounting retained; missing legacy contract/receipt/verdict fields block; no silent approval or dispatch | Migration fixtures + restore verification; S7-01, S7-03–04 |
| AC-16 | FR-06 | Diagnose dependency, capacity, receipt, check, scope, and review blockers | Human and JSON views agree and identify request/task/check plus concrete remedy | Local public status/doctor tests; S7-05 |
| AC-17 | FR-06, NFR-02, NFR-04 | Doctor on an uninitialized repo; status of archived request; unverified host | No request/reservation/worker/history mutation; bounded output; secrets absent; host capabilities honestly labeled | Before/after snapshots, zero-call assertions, output review; S7-05 |
| AC-18 | NFR-01, NFR-02, NFR-04 | Bounded batches, malformed/wrong-request receipts, unsupported native adapter | Progress persists across passes; invalid identity rejected; no unverified native mutation or credential logging | Local reducer/adapter and bounded-call tests; S7-02 |

## Evidence record format

Each row records task ID, source commit plus patch digest when the tree is dirty, OS/Python versions, exact command/scenario, expected versus observed result, sanitized evidence path, reviewer, and status (`pending`, `passed`, `failed`, or `blocked`). Include artifact checksum for package checks. A skipped/expected-failure test is not a passed row. Native receipts, if collected later, require a separate host revision and certification record.
