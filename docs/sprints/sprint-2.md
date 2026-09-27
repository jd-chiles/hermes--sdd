# Sprint 2 — release hardening and host integration

Status: in progress

## Objective

Prove that the public artifact loads through Hermes, preserve the host/plugin boundary, and make release checks reproducible without importing the source checkout.

## Work started

- Add a deterministic source artifact builder.
- Add an artifact smoke test that extracts the tarball and runs Hermes Plugin Doctor and validation against the extracted tree.
- Verify clean pinned installation from GitHub in an isolated Hermes home.
- Make board task recovery idempotent by reconciling stable task keys before creating native tasks.
- Exercise the local request → specification → engineer result → independent review → evidence → acceptance slice.
- Add a three-platform CI matrix, including a Windows WSL2 host-contract job.
- Add profile-preservation smoke coverage in an isolated Hermes home.
- Keep the SDD ledger independent from Hermes' database and use only documented plugin/dispatch interfaces.

## Remaining acceptance criteria

- [x] Cross-platform artifact, repository, and host-contract checks are automated for Linux, macOS, and Windows through WSL2 in CI.
- [x] A clean profile can install and enable the pinned artifact without manual config edits.
- [x] Profile-preservation smoke coverage verifies unrelated profile configuration remains unchanged in an isolated Hermes home.
- [x] The local SDD kernel completes a small regression fix through request → specification → worker result → review → evidence → acceptance.
- [x] Interrupted dispatch can recover without duplicate task creation or lost ledger artifacts.
- [x] Release documentation includes the exact immutable install command and known compatibility gates.

## Exit evidence

The release candidate must include the artifact SHA-256, Plugin Doctor output, validation output, unit-test output, and a short list of any host limitations. A green source-tree test is not sufficient.
