# Sprint 7 verification plan

## Baseline and reporting

The preceding implementation turn reported 72 discovered tests: 71 ordinary passes and one expected failure. Source inspection confirms only the scheduler case in `tests/test_sprint6_pending.py` retains `@unittest.expectedFailure`; the empty/no-op case is ordinary coverage. Do not report the expected failure as a pass or the working-tree changes as present in the baseline commit.

Record every run against an implementation commit plus patch digest for uncommitted work. Use [the acceptance matrix](acceptance-matrix.md) as the evidence checklist. This documentation revision introduces no runtime fixes and requires no rerun of the runtime suite by itself.

## Gate 1 — Local regression and integration checks

After implementation changes, run:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q sdd_hermes scripts tests
git diff --check
```

Both original Sprint 6 regression cases must finish as ordinary passes. Remove the scheduler expected-failure marker only when the dependency-aware behavior is implemented. Do not weaken assertions to achieve a green summary.

Required test groups:

- Scheduler: all graph shapes, product joins in both completion orders, unknown parents/cycles, cap exhaustion, ownership conflicts, concurrent coordinators, paused/terminal requests, and restart.
- Receipts: duplicate/conflicting identity, late old-attempt receipts, wrong request/task, failure/interruption, unknown elapsed time, overrun, and bounded batch processing.
- Crash points: before intent commit, after intent before native response, after native creation before local receipt, and after receipt commit before wake-up processing. Assert launch counts, reservation totals, consumed runtime, and events after recovery.
- Acceptance: finalized required checks, omitted/replaced checks, stale/failed evidence, explicit verdicts, same actor, revised specs, and no-change outcomes.
- Scope: real temporary Git repositories with initial dirty trees, additions/deletions/renames/untracked files, omissions, and unsupported/missing baselines.
- Migration: populated schema-v6 state, retained v5 fixture coverage, partial failure, repeat migration, future schema refusal, and backup restoration. Compare historical rows/counters before and after.
- Diagnostics: human/JSON agreement, actionable codes/remedies, uninitialized and archived requests, bounded output, no dispatch/state mutation, and credential-safe content.

Use a deterministic bridge simulator with controllable native task/attempt IDs, delayed/duplicate receipts, and injected failures. Inspect SQLite and event records through public service journeys as well as focused ledger tests. Temporary repositories, profiles, and homes keep user data out of test mutations.

## Gate 2 — Artifact checks

Run the existing packaging suite through unittest discovery. Verify equivalent output paths and symlink aliases still exclude prior artifacts, preserve source-symlink rejection, and produce deterministic digests. Build an archive in a temporary output directory and inspect its manifest; record the archive checksum. Imported candidate code must not accidentally resolve through the source checkout when testing the artifact.

Existing `scripts/package_release.py` builds a source artifact. Existing `scripts/host_smoke.py` needs a functioning Hermes runtime and does not by itself prove workflow completion. A blocked host smoke is recorded separately from local package results.

## Gate 3 — Review and carry-forward report

An independent reviewer evaluates the final implementation against requirements and matrix rows, with particular attention to transaction/external-call ordering, stale receipt identity, contract weakening, and migration rollback. Capture findings and their resolution; do not invent a reviewer sign-off when none was performed.

S7-06 produces a local go/no-go report with matrix status, commands/results, test counts including failures/skips, migration/restore instructions, artifact digest, and unresolved external gates. All local requirements must pass before local sprint completion. Update Sprint 6 carry-forward status only for the portions actually implemented.

## Native host boundary

The last inventory reported missing `ruamel.yaml`; it was not a fresh check for this draft. Native certification is outside Sprint 7's local scope and remains in Sprint 6. A successful fake bridge or source-parser probe must not enable unverified operations or establish interruption/deadline support. Refresh host inventory and collect actual attempt/lifecycle receipts before a later production support claim.

## Documentation validation

For this package, validate relative links, unique requirement/task/acceptance IDs, full matrix coverage, valid task references, and an acyclic dependency graph. Run `git diff --check`. Keep reported implementation evidence distinct from documentation checks.
