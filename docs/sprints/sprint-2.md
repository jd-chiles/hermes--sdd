# Sprint 2 — release hardening and host integration

Status: in progress

## Objective

Prove that the public artifact loads through Hermes, preserve the host/plugin boundary, and make release checks reproducible without importing the source checkout.

## Work started

- Add a deterministic source artifact builder.
- Add an artifact smoke test that extracts the tarball and runs Hermes Plugin Doctor and validation against the extracted tree.
- Keep the SDD ledger independent from Hermes' database and use only documented plugin/dispatch interfaces.

## Remaining acceptance criteria

- [ ] Artifact smoke test passes on Linux, macOS, and Windows through WSL2.
- [ ] A clean profile can install and enable the pinned artifact without manual config edits.
- [ ] Existing profiles, credentials, defaults, and unrelated plugins remain unchanged.
- [ ] A small regression fix completes through request → specification → worker → review → evidence → acceptance.
- [ ] Interrupted dispatch can recover without duplicate task creation or lost ledger artifacts.
- [ ] Release documentation includes the exact immutable install command and known compatibility gates.

## Exit evidence

The release candidate must include the artifact SHA-256, Plugin Doctor output, validation output, unit-test output, and a short list of any host limitations. A green source-tree test is not sufficient.
