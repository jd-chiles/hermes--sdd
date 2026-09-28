# Hermes SDD Team implementation plan

## Delivered in this slice

1. Native plugin packaging with `plugin.yaml`, Python entry point, slash command, CLI command tree, tools, and bundled focused skills.
2. Adaptive intake for bugfix, feature, and new-product requests with stable requirement and task IDs.
3. Human-readable specifications under `docs/sdd/features/<slug>/`.
4. Transactional SQLite ledger under `.sdd/hermes/`, append-only JSONL events, immutable attempts/evidence, project leases, and idempotent operation IDs.
5. Explicit file ownership admission that rejects overlapping worker claims and path traversal.
6. Verification runner that records command, cwd, exit status, bounded output, duration, and content fingerprints.
7. Project acceptance evaluation that requires current required evidence, passing checks, engineer and independent reviewer submissions, and matching fingerprints.
8. Native Hermes bridge that uses `ctx.dispatch_tool("terminal", ...)` and explicit `--board` arguments; it never writes Hermes' database.
9. Pause, resume, status, and doctor surfaces with visible limits and blockers.

## Current sprint

[Sprint 7](sprints/sprint-7.md) targets dependency-aware scheduling, durable completion receipts, finalized verification contracts, explicit review, and associated diagnostics. Its [full development package](sdd/features/sprint-7-contract-enforcement/spec.md) defines the architecture, migration, stable tasks, and 18 acceptance scenarios. Implementation has partially started with basic empty-submission guards; remaining sprint gates are pending. [Sprint 6](sprints/sprint-6.md) retains broader production-readiness work and native host certification.

## Release and follow-up gates (see Sprint 2 for collected evidence)

- Exercise actual plugin installation and `hermes plugins doctor` against the minimum supported Hermes revision.
- Replace the profile recipe placeholder with the host's supported profile provisioning API and test existing-profile preservation.
- Add native lifecycle hooks for task review transitions and worker interruption once the target Hermes revision is pinned.
- Add managed Python/JavaScript dependency adapters that detect existing tools and route installation through Hermes approvals.
- Add browser evidence adapters and cross-platform smoke tests for Linux, macOS, and WSL2.
- Package the release artifact and run a clean-install smoke test against the artifact, not the source checkout.
