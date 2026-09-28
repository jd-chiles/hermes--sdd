# P0 host-backed execution

- Mode: `feature`
- Specification revision: `1`
- Delivery boundary: verified local repository change; no automatic commit, PR, deployment, or publication.

## Objective

Make tier routing, failure recovery, and native dispatch safe under provider failures, interrupted calls, restarts, and ambiguous host receipts.

## Stable task graph

- **P0-ROUTE** — Resolve authorized low/med/high routes and report configured, shared, unavailable, and unverified states.
- **P0-RECOVERY** (depends on P0-ROUTE) — Persist failure classification and recovery decisions without blind retries or secret storage.
- **P0-DISPATCH** (depends on P0-ROUTE) — Make native dispatch intent idempotent, reconcile interrupted creation, and renew leases.
- **P0-RELEASE** (depends on P0-ROUTE, P0-RECOVERY, P0-DISPATCH) — Add regression coverage and document host verification limits.

## Acceptance criteria

- Route configuration never masquerades as effective host routing; unsupported or shared routes are explicit.
- Provider/configuration/capability/task/environment/ambiguous failures produce durable, actionable states.
- Repeated recovery with the same operation does not consume another native launch.
- An ambiguous dispatch is reconciled before another native task can be created.
- Lease renewal is owner-checked and safe after restart.
- Existing tests and the new P0 regression matrix pass.
