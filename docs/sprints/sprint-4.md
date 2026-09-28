# Sprint 4 — durable recovery budgets and release readiness

Status: active, 2026-09-28. Local budget, cooldown, effective-route receipt, native idempotency, and native recovery promotion work is implemented and validated; installed-host certification remains open.

## Objective

Complete the local recovery state machine so provider failures cannot trigger blind retries, budgets survive restarts, sibling tasks observe route cooldowns, and native dispatch receipts preserve requested/effective route evidence.

## Delivered this cycle

- Schema v4 adds task repair/provider-recovery budgets and route breaker state.
- Provider-transient failures open a durable 60-second route cooldown.
- Structured `Retry-After` values can extend or shorten the cooldown; worker prose is ignored.
- Expired breakers allow exactly one durable half-open probe until a successful receipt heals the route.
- Recovery admission rejects paused projects, active cooldowns, missing actionable changes, unsupported failure classes, and exhausted budgets.
- Repair and provider-recovery counters are separate and restart-safe.
- Dispatch completion stores an optional effective-route receipt without credentials.
- Confirmed dispatch completion increments native-launch accounting; ambiguous or failed creation does not.
- Native task creation propagates the durable operation ID as `--idempotency-key` and configures the host consecutive-failure breaker with `max_native_retries`.
- Native recovery promotes the existing task only after durable SDD recovery admission; no duplicate task is created.
- Added `sdd_admit_recovery` for explicit recovery admission.
- Added restart, sibling-cooldown, budget-exhaustion, and receipt persistence regressions.

## Remaining backlog

| ID | Priority | Deliverable | Status |
| --- | --- | --- | --- |
| S4-05 | P1 | Verify effective provider/model routing and native attempt semantics against the pinned Hermes host. | Open; host access required |
| S4-06 | P1 | Replace fixed cooldown with host `Retry-After` and health-signal evidence when available. | Local fallback implemented; host evidence open |
| S4-07 | P1 | Connect recovery admission to native launch accounting and provider circuit-breaker half-open probes. | Local accounting/probe gate implemented; host semantics open |
| S4-08 | P2 | Run extracted-artifact, clean-install, profile-preservation, and WSL2 release checks. | Open; host access required |

## Verification evidence

- Local suite: 49 tests passed; Python compilation and diff checks passed.
- Pinned Hermes source contract: passed at `8f897d2d23a338f7a062ebc4fa7aedc287d087de`; confirms `--idempotency-key`, `--max-retries`, and provider/model worker propagation without launching a worker.
- Artifact smoke: attempted and blocked because the installed Hermes runtime cannot acquire its read-only `.install.lock`/`pm-runtime/.prepare.lock`. Plugin Doctor and validation did not execute.
- Clean-install and profile-preservation were attempted against immutable revision `16066ad5f311d3f4d9908285d610e68e79ea8735`; both were blocked while Hermes tried to download its runtime because DNS is unavailable, leaving `ruamel` unavailable in the incomplete host environment. Profile sentinels remained preserved.
- WSL2 validation is defined in `.github/workflows/sprint2.yml` but cannot execute from this Linux workspace; it remains a CI-host gate.

## Exit criteria

- No retry can pass recovery admission without a durable budget reservation and actionable change.
- Provider failures coordinate through one route-level breaker across service restarts.
- Effective route receipts are persisted when supplied and remain explicitly unverified when absent.
- Pinned-host routing and native attempt-cap tests pass before release claims are made.
