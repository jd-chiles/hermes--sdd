# Sprint 5 architecture

## Lifecycle model

```text
planned → dispatching → running → review → accepted → closed
    │          │           │         │
    └──────────┴───────────┴─────────┴── blocked / paused / reconciling
```

`closed` is terminal for a project identity. A new request gets a new project identity and active root association; old rows remain addressable by their historical project ID.

## Admission boundary

All worker-limit and runtime-limit decisions occur before native task creation or native promotion:

1. Acquire project lease.
2. Verify project is active and unpaused.
3. Reconcile current native receipts.
4. Atomically reserve worker and runtime capacity.
5. Record operation ID and reservation.
6. Dispatch through the Hermes bridge.
7. Commit native receipt or persist an ambiguous blocker.

No limit check may occur only in status rendering or after native work has started.

## Durable data additions

Implemented tables/records:

- `worker_reservations`: task, coordinator, operation ID, state, acquired/ released timestamps.
- `runtime_reservations`: task, reserved seconds, actual seconds, state, operation ID.
- `limit_blockers`: limit name, observed usage, cap, unblock condition, lifecycle event.

Planned for the host lifecycle slice:

- `host_capabilities`: pinned host revision, capability name, result, evidence, verification timestamp.

The implementation may combine these records where transactional ownership is preserved, but must not move authoritative state into JSONL or Hermes’ database.

## Host lifecycle adapter

The bridge should expose narrow capability methods such as `block_task`, `promote_task`, and `transition_review`. Each method must:

- use explicit board and native task IDs;
- parse the documented JSON envelope;
- reject nonzero, incomplete, or ambiguous responses;
- be disabled until the pinned-host contract verifies support.

## Compatibility and migration

Schema changes must be additive and start existing ledgers with zero reservations and no blockers. Closed projects must not be migrated by rewriting historical task or evidence rows. A failed migration blocks the operation before dispatch.
