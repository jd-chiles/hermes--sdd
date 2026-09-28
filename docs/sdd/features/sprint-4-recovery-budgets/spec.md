# Sprint 4 — durable recovery budgets and release readiness

- Mode: `feature`
- Specification revision: `1`
- Delivery boundary: verified local repository change; no automatic commit, PR, deployment, or publication.

## Objective

Finish the local recovery state machine so provider failures cannot cause blind retries, budgets survive restarts, route cooldowns coordinate sibling tasks, and successful native dispatches retain an effective-route receipt when the host provides one.

## Stable task graph

- **S4-01** — Persist repair/provider/native launch budgets and route breaker state.
- **S4-02** (depends on S4-01) — Gate recovery admission on pause, cooldown, budget, and actionable-change conditions.
- **S4-03** (depends on S4-01) — Persist requested/effective route receipts on dispatch completion.
- **S4-04** (depends on S4-02, S4-03) — Add restart/concurrency regression coverage and update release documentation.

## Acceptance criteria

- Provider failures open a durable route cooldown; sibling recovery attempts observe the same breaker.
- A recovery with no actionable change is rejected without consuming a budget or native launch.
- Repair and provider-recovery counters are distinct and survive a new service instance.
- Ambiguous dispatch remains `reconcile_required` and cannot reserve a recovery launch.
- Effective route receipts are persisted only when returned by the host; missing receipts remain explicitly unverified.
- Existing tests and the Sprint 4 regression matrix pass.
