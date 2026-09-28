# Task difficulty, model routing, and escalation

Status: Sprint 4 implementation slice, 2026-09-28. Per-task difficulty, configured route resolution, durable failure decisions, idempotent dispatch intents, local recovery budgets, route cooldowns, and optional effective-route receipts are implemented locally. Native attempt-cap integration, host health/Retry-After semantics, and pinned-host certification remain release gates. This document does not enable routing or reset live task budgets.

## Current gap

`planning.classify` selects bugfix/feature/product workflows from request text. Per-task difficulty is assessed separately by `difficulty.assess` from explicit dimensions, with med as the unassessed default. `SDDService.sync_board` assigns role names and now propagates configured provider/model routes, a durable idempotency key, and the native consecutive-failure breaker. Profile provisioning creates/enables role profiles without verifying the effective provider/model. Local failure taxonomy, route breakers, recovery budgets, effective-route receipts, and native promotion admission are implemented; live provider authorization, host-effective route verification, and native attempt receipts remain release gates.

The user's task-240 incident occurred in the OpenCode version of the plugin, not this Hermes implementation. It reports provider trouble, a delegation interface with no model parameter, identical inherited free-model routes across tiers, and one remaining native attempt. Treat it as a cross-host failure scenario to prevent in Hermes, not evidence of Hermes runtime behavior. This repository independently lacks effective tier routing and escalation machinery. A source-contract test at Hermes revision `8f897d2d23a338f7a062ebc4fa7aedc287d087de` confirms Kanban model/provider overrides reach the worker argv builder; live effective-route verification remains open. Hermes model selection, effective-route reporting, and native attempt semantics must be verified against its supported host interfaces; do not assume OpenCode's constraints apply. The incident's provider diagnosis has not been independently verified from runtime logs. Successful siblings alone do not prove a provider outage.

## Difficulty is independent of workflow and role

Assess each task after repository inspection using scope, uncertainty, coupling, consequence of error, and verification difficulty. Store the tier, reasons, evidence, policy version, and any explicit override. Use `low`, `med`, and `high` as canonical values; accept `medium` as an input alias. A short bugfix can be high difficulty; a product's read-only checklist can be low.

| Tier | Admission rubric | Execution requirements |
| --- | --- | --- |
| low | All dimensions are low: bounded known procedure, clear inputs and expected result, local scope, low consequence, direct checks. | Smallest authorized route demonstrated adequate for the required tools/context; explicit scope and checks. |
| med | At least one dimension is medium, none high; bounded implementation or investigation, several related files, some design decisions, known integration points. Unknown dimensions default to med pending inspection. | Implementation plan and regression coverage; route capable of the task's tools/context. |
| high | Any dimension is high: cross-component uncertainty, concurrency, consequential migration or permission changes, large impact, or difficult correctness proof. | Decompose where possible, record architecture/risks, use an explicitly configured capable route, and preserve independent review and acceptance. |

Use the highest assessed dimension, not an average that hides risk. Roles do not imply difficulty. Read-only work is not automatically low if the analysis is complex. Tier changes require a reason and retain history. Do not increase difficulty because a provider is unavailable. All tiers retain the same acceptance guarantees.

## Resolve a real route before dispatch

A route is an authorized configuration identified by provider, endpoint identity, model, relevant reasoning settings, and configuration version. Never persist credentials in the ledger. Profile names and low/med/high labels are not route identities. Record requested and effective routes separately.

1. Read the user's configured tier-to-route mappings and permitted fallbacks. Configuration presence does not by itself authorize paid usage; apply existing cost/provider authorization and task capability constraints.
2. Probe the pinned host's supported dispatch/profile interface. A missing delegation model parameter may still permit an explicitly selected preconfigured profile, but that must be proven by a host-contract test. Do not invent a model flag or mutate shared profiles.
3. Resolve the effective route and verify the host can apply it. Fail visibly before dispatch if the requested capability cannot be expressed or confirmed. Report `routing_unavailable` with the missing capability and available remedies.
4. If all tiers resolve to one route, report `shared_route` and `escalation_available: false` when no distinct authorized fallback exists. Shared routing is allowed if adequate for the tasks; it is not model escalation.
5. Record dispatch intent, operation ID, native task/attempt ID, policy version, requested/effective route, and budget reservation atomically. Reconcile ambiguous dispatch receipts before another launch.

Use supported host configuration only. Keep role identity separate from route selection so independent review remains meaningful. Host support and actual effective-route reporting are release gates, not assumptions.

## Failure classification drives recovery

Store structured host error codes, phase, provider/route identity, timestamps, native attempt ID, and redacted diagnostic evidence. Do not classify by a worker's prose alone.

| Failure class | Evidence / examples | Action |
| --- | --- | --- |
| provider_transient | Provider 429/5xx, confirmed outage, connection failure before useful work | Preserve difficulty; open a cooldown for the affected route; select a distinct healthy authorized route if available. Otherwise wait for Retry-After/cooldown plus a fresh health signal. |
| provider_configuration | Authentication, account quota, unknown/unavailable model, unsupported provider configuration | Block the affected route until configuration/version changes or choose a proven authorized fallback. Repeated delay alone does not fix these errors. |
| capability_mismatch | Confirmed missing tool support, context capacity, or task-required modality | Choose a compatible authorized route or decompose the task. Do not retry the unchanged incompatible configuration. |
| task_defect | Reproducible failing acceptance check or reviewer finding against a completed result | Use a bounded repair cycle with a changed plan. Reassess difficulty from the actual defect; promote low → med → high only when justified. At high, decompose or surface a concrete blocker. |
| environment_or_permission | Missing dependency, unavailable workspace, denied required operation | Resolve the specific prerequisite within existing authorization or block. A stronger model is not the remedy. |
| unknown_or_ambiguous | Worker disappears, incomplete receipt, timeout with uncertain progress | Reconcile native state and preserve artifacts. Gather evidence before relaunch; do not assume task defect or provider outage. |

One task can have several failure events; each event has one primary classification and supporting evidence. Reclassification is an appended decision, not a rewritten record.

## Retry budgets and state transitions

Discover whether the supported Hermes host exposes native attempt limits and receipts, and document their semantics. If it does, honor them; if it does not, enforce an explicit durable plugin launch cap and report that native capacity is unavailable rather than fabricating it. If capacity is unknown because a required host query failed, block until reconciled. Keep distinct counters for native launch attempts (host authoritative where supported), task repair cycles, provider recovery launches, and total runtime/cost. Provider failures do not consume the plugin's task-defect repair counter, but any host-consumed attempt still counts against the native cap. Never refund, reset, clone tasks to bypass, or invent additional native attempts.

`failed → classified → waiting_provider | blocked_configuration | blocked_capability | repair_ready | reconcile_required`

A launch is permitted only after all gates pass: not paused, dependencies satisfied, ownership/lease valid, native attempt capacity available, class-specific budget available, total budget available, and an actionable recovery change recorded. Then transition through `dispatch_pending → running` using an idempotent operation ID. Use bounded exponential backoff with jitter and honor Retry-After; waking a timer alone must not automatically spend an attempt.

For repeated provider failures, the actionable change must be a distinct effective route, a corrected configuration, or a fresh recovery/health signal after cooldown. A new profile label pointing at the same failing provider/model does not qualify. Coordinate a route-level circuit breaker so sibling tasks do not each probe and spend their last attempt. A half-open probe also needs explicit budget accounting; prefer health checks that do not consume native task attempts when supported.

Defaults and caps must be explicit in the saved policy. Preserve the existing proposed two-repair cap pending implementation, configure provider recovery separately, and never allow a new counter to extend the native cap. At budget exhaustion or when no executable route exists, persist the blocker and the condition that can unblock it; resume reevaluates those conditions without resetting counters.

## Required regression adapted from OpenCode task 240

This is a synthetic Hermes adapter regression derived from the OpenCode incident, not a reproduced Hermes failure. Exercise both a host-reported attempt cap and the plugin-owned cap when the host has no equivalent.

Given a low-difficulty read-only checklist, structured evidence of provider failure, all tier profiles resolving to the same failing route, no verified alternate routing capability, and one native attempt remaining:

- Keep difficulty low and classify the failure as operational.
- Set `waiting_provider` or `blocked_capability` as supported by the evidence; report that no distinct executable authorized route is available.
- Make zero delegation/retry calls and preserve the remaining native attempt. Do not consume a task repair cycle.
- Repeated recover calls, restarts, and sibling failures leave that result unchanged.
- An alternate profile name with the same effective route does not unblock it.
- A supported distinct authorized healthy route, or verified recovery of the original provider after cooldown, makes it eligible for exactly one launch, subject to all budget/dependency gates.
- Persist the actual route and native attempt receipt. If dispatch completion is ambiguous, reconcile instead of spending another attempt.

## Test and release matrix

- Tier tables cover short complex bugs, simple product checklists, unknown scope, explicit overrides, and high-consequence work; classification survives restart.
- Failure tables cover transient provider errors, auth/quota failures, task defects, missing dependencies, capability mismatch, and unknown/ambiguous failures.
- Routing tests cover unsupported host interfaces, shared routes, unauthorized/cost-disallowed fallbacks, changed profile labels, actual effective-route changes, and privacy of recorded metadata.
- Budget/state tests cover the last native attempt, exhausted budgets, concurrent recovery, repeated operation IDs, restarts, pause, Retry-After, and circuit-breaker coordination.
- Pinned-host tests prove configuration reaches the worker and verify native attempt accounting. Mock-only tests cannot close this item.
