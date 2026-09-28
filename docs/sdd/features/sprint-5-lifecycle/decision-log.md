# Sprint 5 decision log

## D-01 — Close is explicit

An accepted project must be explicitly closed. Acceptance alone does not silently archive the request, because operators need a visible lifecycle event and a deliberate boundary before starting another request.

## D-02 — History is append-only

Closing archives the project identity rather than deleting or rewriting its rows. This keeps acceptance evidence auditable and makes recovery of historical context possible.

## D-03 — Limits are admission controls

Worker and runtime limits are enforced before native dispatch. Status-only warnings are insufficient because they permit the exact over-admission the limits are intended to prevent.

## D-04 — Host callbacks are capability-gated

Role names and profile creation do not prove lifecycle support. Native callback behavior is enabled only after a pinned source/host contract verifies the command, arguments, and receipt semantics.
