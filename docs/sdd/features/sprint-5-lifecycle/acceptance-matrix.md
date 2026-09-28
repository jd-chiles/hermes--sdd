# Sprint 5 acceptance matrix

| ID | Scenario | Expected result | Evidence |
| --- | --- | --- | --- |
| AC-01 | Close planned project | Reject; stage remains planned | Unit test + status |
| AC-02 | Close accepted project | Append close event; stage becomes closed | Ledger event + status |
| AC-03 | Repeat close | Return idempotent success; no second mutation | Operation/event count |
| AC-04 | Initialize after close | New project ID and active root; old rows preserved | SQLite history query |
| AC-05 | Two coordinators admit at worker cap | One winner; one durable blocker | Concurrent test |
| AC-06 | Admit while paused | Reject before reservation/native call | Unit test + mock bridge |
| AC-07 | Runtime cap exhausted | Reject with usage/cap/unblock details | Budget test |
| AC-08 | Restart with active reservation | Reservation and usage remain authoritative | Restart test |
| AC-09 | Duplicate admission operation | Return original result; no extra reservation | Idempotency test |
| AC-10 | Unsupported host lifecycle callback | Report unverified/unsupported; no native mutation | Pinned-host contract |
| AC-11 | Ambiguous native lifecycle response | Persist reconcile blocker; no retry | Envelope regression |
| AC-12 | Existing acceptance flow | All prior acceptance tests remain green | Full test suite |

## Required evidence ordering

1. Unit and concurrency tests.
2. Python compilation and diff checks.
3. Pinned-host lifecycle capability contract.
4. Extracted-artifact Plugin Doctor/validation.
5. Cross-platform CI, including WSL2.

Mock-only evidence cannot close AC-10 or any native lifecycle claim.
