# Hermes SDD Team

Hermes SDD Team turns a development request into a durable, verified local repository change. It adapts the workflow to the request: a regression fix gets a short implementation/review/acceptance path, a feature gets requirements and architecture tasks, and a new product gets UX and incremental backlog tasks.

## Install

Use a released immutable revision when publishing:

```text
hermes plugins install <owner>/hermes-sdd-team --ref <release-sha> --enable
```

The package is a native Hermes plugin (`plugin.yaml` + `register(ctx)`). It does not require a copied prompt, manual profile configuration, separate MCP server, or provider account. Execution currently uses assigned role profiles; their effective model configuration is not yet verified by the plugin. The current repository is an implementation slice and still requires host compatibility verification against the target Hermes release before public publication.

## Commands

```text
/sdd plan Add a validation rule
/sdd build Fix the parser regression
/sdd fix Fix the parser regression
/sdd status
/sdd pause
/sdd resume
/sdd recover
/sdd doctor
```

Equivalent terminal commands are available under `hermes sdd …`.

`plan` writes a human-readable specification and stable task graph without dispatching work. `build` initializes the project-owned board and dispatches the graph through Hermes' supported terminal/tool boundary when available. `status` distinguishes planned, queued, running, review, submitted, and accepted states. A worker result is a submission, not proof of acceptance.

## Project data

- Specifications: `docs/sdd/features/<slug>/spec.md`
- Plugin ledger and JSONL event export: `.sdd/hermes/`
- Native board: created with an explicit `sdd-<slug>` board name; Hermes owns its persistence.

The SQLite ledger records stable task IDs, immutable attempts, immutable verification evidence, file ownership, operation IDs, and coordinator leases. It never edits Hermes' database. Ownership rules serialize overlapping files but are not an OS security sandbox; Hermes' normal permission system remains authoritative.

## Acceptance contract

Acceptance requires every required criterion to have current evidence, each required command to pass, an engineer submission, an independent reviewer submission, and fingerprints matching the repository after verification. Stale attempts, wrong specification revisions, duplicate operation IDs, and overlapping ownership are rejected.

No automatic commits, pull requests, deployment, publication, or launch communication are performed.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q sdd_hermes scripts
```

Sprint 3 is underway: see the [prioritized review](docs/reviews/sprint-3-review.md) and [sprint backlog](docs/sprints/sprint-3.md).

Release checks build and inspect the real artifact:

```bash
python3 scripts/host_smoke.py
python3 scripts/clean_install_smoke.py \
  --repo jd-chiles/hermes-sdd-team \
  --ref 400309b27a07d47a7a723ab8a205c343b4e920fe
python3 scripts/profile_preservation_smoke.py \
  --repo jd-chiles/hermes-sdd-team \
  --ref 400309b27a07d47a7a723ab8a205c343b4e920fe
```

The smoke test extracts a tarball into a temporary directory and runs Hermes Plugin Doctor and validation there, so success does not depend on importing the source checkout.

The `skills/` directory contains focused role guidance. Hermes loads only the skills registered by the plugin and can add them to task cards through its native Kanban mechanisms.

Release archives include explicit source directories and exclude local workspace metadata and prior build outputs. Tar metadata and gzip headers are normalized for repeatable hashes; source symlinks are rejected. Scripts in the archive are invoked with Python.

Task difficulty is assessed separately from bugfix/feature/product workflow selection. `sdd_initialize` accepts `task_assessments` keyed by stable task ID (for example, `T-001`), with `dimensions` (`scope`, `uncertainty`, `coupling`, `consequence`, `verification`) rated `low`, `med`, or `high`, plus a `rationale`. Unknown dimensions default to `med`; the highest risk determines the tier. Status reports configured routes separately from effective host routes. Automatic escalation remains gated on pinned-host route receipts and native attempt semantics.

Schema v2 binds submissions to file fingerprints and the current engineer attempts. Existing attempts without that context must be resubmitted and verified before acceptance. Reviewers must use a different actor identity and cover the engineer's submitted files. Verification file lists must match the submission, and every declared check must have passing evidence.
