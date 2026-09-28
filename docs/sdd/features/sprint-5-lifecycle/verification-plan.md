# Sprint 5 verification plan

## Local checks

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q sdd_hermes scripts
git diff --check
```

## Targeted test groups

- `test_coordination.py`: lifecycle, concurrency, reservations, blockers, and restart behavior.
- `test_acceptance.py`: unchanged acceptance invariants after lifecycle transitions.
- `test_commands.py`: `/sdd close`, CLI close, and limit-denial surfaces.
- New lifecycle/limits tests: schema migration, idempotent reservations, runtime accounting, and host callback fail-closed behavior.

## Host checks

- Add a pinned Hermes source-contract check for lifecycle commands and response envelopes.
- Run Plugin Doctor and validation against the extracted artifact.
- Run clean-install and profile-preservation checks against the immutable release revision.
- Confirm Linux, macOS, and WSL2 CI results before declaring host lifecycle support.

## Failure handling

If host preparation, dependency download, or WSL2 is unavailable, preserve the source and local evidence, mark the host criterion blocked, and do not claim release certification.
