# Sprint 6 decision log

Status: design decisions for implementation. Open host questions remain gates, not implied capabilities.

## D-01 — Follow Sprint 5 without rewriting its history

Create Sprint 6 for the five production-readiness priorities. Carry forward unfinished lifecycle/history work and correct its discovered gaps. Retain Sprint 5 artifacts as historical evidence; link forward to the new acceptance gates.

## D-02 — Reserve capacity for executable work

Queued graph nodes do not consume worker slots. This refines Sprint 5's admission-before-native-creation rule: native creation may precede admission only when the pinned host proves the created card cannot execute. Otherwise defer native creation. All actual launch and promotion paths require atomic admission.

## D-03 — Verify host semantics before choosing the adapter

Callbacks and bounded polling are both acceptable if they satisfy receipt and recovery requirements. S6-01 must resolve: whether create auto-launches; how runnable state is controlled; stable attempt identity and idempotency scope; elapsed-time availability; interruption/deadline guarantees; review transitions; and CLI dispatch access. Until resolved, local simulation is useful but native support remains unverified. No minimum host version is invented in this package.

## D-04 — Separate repository association from request identity

A root hash cannot identify every successive request. Use immutable request IDs with an explicit active association and request-scoped native/artifact names. Preserve existing IDs and historical references in migration. Closed and abandoned outcomes are terminal.

## D-05 — Runtime means cumulative worker-seconds

Completion converts commitments to actual consumption; it does not refund consumed time. Unknown receipts remain conservative commitments. Track wall-clock duration separately. Hard termination claims require a verified deadline/interruption contract; admission accounting alone is insufficient.

## D-06 — Acceptance is a versioned contract

Required checks belong to the spec, not the implementation's self-reported list. Require complete diff coverage and explicit independent review because passing a command does not prove a natural-language outcome. Permit a separately reported no-change-needed result only with behavior evidence and justification. Initially use Git baselines for diff certification; other repository types remain explicitly unsupported until an equivalent adapter is tested.

## D-07 — Standardize the installed plugin identifier

Use `jd-chiles/hermes--spec-driven-development-plugin` as the canonical repository and `hermes-sdd` as the installed identifier. Align public copy, tool schemas, help, and release metadata. Select the actual candidate version/ref during S6-12; this spec does not create a release.

## D-08 — Public diagnostics are read-only

Doctor/history should explain state without initializing a request, launching work, or changing profiles. Human output and machine JSON share the same result semantics. Support free-form requests through an explicit form and reject command-like typos; settle exact command grammar and documented exit codes in S6-10 with compatibility tests.

## D-09 — Certify the shipped bytes

The candidate digest, not a successful source-checkout import, defines the release evidence. Pin host revisions and verify upgrades. A platform failure must not prevent collecting independent host evidence, but any required failure prevents a ready verdict. Publishing remains a separate action outside this documentation request.
