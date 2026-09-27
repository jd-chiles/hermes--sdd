---
name: sdd-recovery
description: Reconcile interrupted SDD work without losing artifacts or duplicating dispatch.
---

# SDD recovery

Use stable operation IDs and the project-scoped lease. Reconcile native board references with `.sdd/hermes/` rather than resetting state. Pause and resume are idempotent. Preserve ambiguous or corrupt state for diagnosis; never infer completion from a manually completed board card or a missing worker process.
