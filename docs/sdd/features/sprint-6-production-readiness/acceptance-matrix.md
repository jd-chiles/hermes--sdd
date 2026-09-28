# Sprint 6 acceptance matrix

All rows are pending. `Local` means deterministic fixture/integration evidence; `Host` means evidence from the actual extracted candidate on a pinned Hermes host. Local simulations cannot close Host gates.

| ID | Requirements | Scenario | Required result | Evidence / task |
| --- | --- | --- | --- | --- |
| AC-01 | FR-01 | Three-, five-, seven-task workflows at default limits | All finish; waiting dependencies use no active slots; newly eligible work schedules automatically | Local + Host; S6-04–05, S6-11 |
| AC-02 | FR-01, NFR-01 | Concurrent admission and recovery promotion at capacity | No over-admission, duplicate launch, or changed-payload replay | Local concurrency + Host launch receipts; S6-04–05 |
| AC-03 | FR-02, NFR-01 | Crash before/after dispatch receipt; duplicate/out-of-order completion | One native attempt per intent; correct reservation released once; durable state/event consistency | Local fault injection + Host restart; S6-05 |
| AC-04 | FR-02, FR-12 | Missing capability, ambiguous native response, or pause without confirmed stop | No unsupported mutation/retry; capacity retained where outcome unknown; clear blocker and remedy | Local + Host capability report; S6-01, S6-05, S6-10 |
| AC-05 | FR-03 | Complete 10 seconds under a 10-second total cap, then request more | Reject new positive commitment; restart does not refund usage | Local ledger assertions; S6-05 |
| AC-06 | FR-03, NFR-03 | Per-task retries, overlapping workers, elapsed overrun, and unknown duration | Cumulative worker-seconds counted; limits block further admission; deadlines enforced only with proven host support | Local + Host timed/interruption receipts; S6-05, S6-11 |
| AC-07 | FR-04, NFR-01 | Ten sequential requests; replay second request; restart; concurrent initialization; repeated titles | One active identity; no uniqueness errors, duplicate cards, stage reset, or overwritten spec artifacts | Local + Host lifecycle sequence; S6-03, S6-06, S6-11 |
| AC-08 | FR-05 | Close stale/paused/active request; repeat close; mutate closed request | Reject invalid close and all terminal mutations; valid close idempotent | Local + Host close scenario; S6-06 |
| AC-09 | FR-05 | Abandon unfinished request with running/ambiguous work, then begin another | Stop admission; terminalize only after reconciliation; retain history; never mark abandoned work accepted | Local + Host interruption; S6-06 |
| AC-10 | FR-05, FR-11 | Inspect prior requests after new initialization | Read-only history returns correct specs, attempts, evidence, outcome, and diagnostics | Local + public command transcript; S6-06, S6-10 |
| AC-11 | FR-06 | Omit/replace a required check; revise spec; require unsupported evidence type | Acceptance blocked; prior evidence cannot satisfy revised contract; actionable reason | Local acceptance integration; S6-07–08 |
| AC-12 | FR-07 | Omit modified/new/deleted/renamed/untracked request files; pre-existing dirty tree | Reject incomplete scope; preserve and distinguish user changes; stale diff rejected | Local real-Git fixtures; S6-07–08 |
| AC-13 | FR-08 | Reviewer requests changes, shares actor, or reviews old implementation | Acceptance rejected despite passing commands | Local acceptance integration; S6-08 |
| AC-14 | FR-06, FR-08 | Empty submission plus unrelated `python -c pass`; legitimate no-change request | First case rejected; second needs behavior evidence, rationale, and independent approval with distinct outcome | Local acceptance integration; S6-08 |
| AC-15 | FR-09 | Rebuild under equivalent output paths and altered timestamps | Artifact/manifest excluded from sources; identical bytes/hash; source symlinks rejected | Linux/macOS/Windows package tests; S6-09 |
| AC-16 | FR-09, FR-10 | Build and install candidate in isolated home | Correct version/tool manifest; exact digest certified; doctor/validation and end-to-end workflow pass without checkout imports | Host per advertised platform; S6-11 |
| AC-17 | FR-10, NFR-02 | Upgrade populated schema v5; repeat migration; fail mid-migration; encounter future schema | IDs/history/counters preserved; legacy contract blockers explicit; failure recoverable; unsupported schema not mutated | Local migration fixtures + Host upgrade; S6-03, S6-11 |
| AC-18 | FR-10 | One unrelated platform fails while another host job is runnable | Independent host evidence still collected; aggregate release gate fails until all advertised targets pass | CI configuration check and actual candidate run; S6-11 |
| AC-19 | FR-11 | CLI/slash/tool plan/build/fix/status/pause/resume/recover/accept/close/history/abandon | Equivalent service semantics; real CLI execution works; human/JSON formats correct; errors exit nonzero on CLI | Local interface tests + Host transcripts; S6-10–11 |
| AC-20 | FR-11 | Help, misspelled command, missing argument, invalid input | No accidental dispatch or traceback; actionable usage; explicit free-form path works | Local public-interface tests; S6-10 |
| AC-21 | FR-12, NFR-03 | Run doctor before initialization; preserve existing profiles; uninstall | No request/worker created; capabilities honest; user profile/work preserved; no credential leakage | Local + isolated Host snapshots/log review; S6-10–12 |
| AC-22 | FR-10, FR-12 | New user follows quickstart with candidate ref | Install, small change, blocker diagnosis, recovery, history, and uninstall reproducible; supported versions/checksums documented | Fresh-home walkthrough and candidate report; S6-12 |
| AC-23 | NFR-01, NFR-03 | Interrupted export, bounded verification output, timeouts, overlapping ownership | Ledger remains authoritative; export rebuilds; execution/output bounded; conflicts rejected; diagnostic secrets excluded | Local fault/concurrency tests + Host permission-boundary check; S6-05, S6-08, S6-11 |

## Evidence record

For each row record: task ID, plugin commit, artifact digest if applicable, host/Python/OS versions, exact command or scenario, expected versus observed result, sanitized evidence location, reviewer, and status (`pending`, `passed`, `failed`, or `blocked`). A skipped required check is not a pass. Changes to supported platforms or acceptance scope require a documented spec revision.
