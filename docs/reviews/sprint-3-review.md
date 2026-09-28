# Sprint 3 project review

Reviewed 2026-09-27 against baseline `03248ae` plus the Sprint 3 kickoff patch. Scope: workflow kernel, host bridge, planning, packaging, tests, CI, and release documentation. This is a project correctness review, not a completed host compatibility certification.

The plugin has a useful separation between its local ledger and Hermes-owned execution, immutable attempt/evidence records, and a small dependency-free implementation. The five existing tests pass. The highest-value next work is making its advertised acceptance and recovery guarantees hold under retries and failures.

## Prioritized findings

| Priority | Finding and source | Impact / evidence | Sprint item |
| --- | --- | --- | --- |
| P1 | `Ledger.accept_project` in `sdd_hermes/core.py` checks for any engineer/reviewer attempt, ignores actor independence and declared checks, and does not restrict evidence to current attempts. | A temporary-repository reproduction accepted a same-actor review with an unexecuted declared check, then accepted a new engineer attempt using the old evidence. Acceptance can be false-positive. | S3-02 |
| P1 | Acceptance evidence queries have no explicit ordering; the specification revision is hard-coded to 1. A failed reevaluation does not clear the persisted accepted stage. | Status can continue reporting accepted after fingerprint validation fails. Verification also accepts its own file list instead of deriving it from the attempt. | S3-02 |
| P1 | `SDDService.sync_board` creates children with no parents if a parent's creation/ID decoding fails; `HermesBridge.find_task` uses substring matching and misses direct list responses. | Failed dispatch may produce runnable dependent tasks; recovery can match a reference to another task's key instead of its identity. The existing recovery test mocks away response parsing. | S3-03 |
| P1 | `Ledger.acquire_ownership` and `acquire_lease` read before opening a write transaction; operation deduplication occurs after ownership mutation. | Concurrent coordinators can race; replaying an operation ID can change ownership even when its event is rejected. SQL inspection; contention behavior needs regression tests. | S3-04 |
| P1 | No difficulty-tier assessment, effective-route resolution, failure taxonomy, or escalation state machine exists in planning/service/bridge. Role profiles do not demonstrate distinct model routes; stored repair limits are unenforced. | The supplied OpenCode task-240 incident motivates a preventative Hermes regression. Local source inspection independently confirms missing routing/escalation machinery; the OpenCode incident does not establish Hermes delegation constraints or native budget semantics. | S3-07, S3-08 |
| P2 | `scripts/package_release.py` recursively packages the workspace and normalizes only tar modification time. | Four regression tests failed before the kickoff fix: repeat builds included outputs, local files entered the archive, gzip/metadata changed hashes, and source symlinks were accepted. Fixed locally in kickoff. | S3-01 |
| P2 | `_cli_handler` has no host dispatch context; `/sdd fix` sets execute false; `recover` checks initialization after acquiring a lease; runtime/repair/worker limits are stored but not enforced. | Documented commands and limits exceed observable behavior. A completed request also prevents initializing a different request indefinitely. | S3-05; lifecycle/limits follow-up |
| P2 | Host CI installs a floating Hermes release and checks the checkout; clean-install/profile scripts are not run in CI. | Compatibility is not reproducible, and archive validation is not a CI release gate. Sprint 2's final WSL2 result remains unconfirmed. | S3-06 |

## Verification and limits

- Baseline: 5 unit tests passed with Python 3.
- Kickoff: 9 unit tests passed, including four packaging regressions; compileall passed.
- Packaged host smoke attempted: both host commands stopped in Hermes runtime preparation because its installation lock files are on a read-only filesystem. Plugin Doctor/validation therefore remain unverified for this patch.
- `gh run view 36349473446` could not connect to `api.github.com`; no updated remote CI conclusion is claimed.
- Managed dependencies, browser evidence, profile model inheritance, task lifecycle callbacks, and multi-request support remain follow-up work. Do not expand those capabilities until acceptance and dispatch invariants are covered.

## Added routing and escalation scope

The [task-tier and escalation contract](../design/task-tiers-and-escalation.md) separates difficulty, route capability, failure cause, and retry accounting. The supplied task-240 incident belongs to the OpenCode version. Its failure pattern is a mandatory preventative Hermes regression, including shared routes and a final permitted launch. Verify Hermes capabilities and use native or plugin-owned launch accounting as supported; do not import OpenCode API assumptions. This is specified work, not an implemented runtime fix.

## Implementation follow-up, batch 1

The findings above describe the reviewed baseline. Sprint 3 now implements current-attempt acceptance and independent review, persisted difficulty assessment, native response/identity parsing, product dependency correction, and atomic ownership/lease admission. See the sprint's implementation batch for validation and remaining work. Effective routing and automatic escalation are still pending. The local Hermes source supports Kanban model/provider overrides; the OpenCode interface limitation does not transfer directly.
