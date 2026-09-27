# Release checklist

Verified release baseline: `2e5103a084cb1ac4611670a8bd4d381956767c03`

Install and enable the exact pushed revision:

```text
hermes plugins install jd-chiles/hermes-sdd-team --ref 2e5103a084cb1ac4611670a8bd4d381956767c03 --enable
```

Source artifact evidence for this revision:

- SHA-256: `2378b285bbdbe42c35128145009a900cfd56c2b82d70c82b603a6ce0f907a391`
- Hermes Plugin Doctor: passed; 10 tools registered.
- Hermes plugin validation: passed.
- Unit suite: 5 tests passed.
- Clean pinned install: passed in an isolated Hermes home; plugin listed as `enabled` and pinned at `2e5103a0`.

Known limitations and remaining release gates:

- The pinned release baseline above is the verified Linux release artifact. Sprint 2 CI now automates repository and Hermes host checks across Linux, macOS, and Windows through WSL2.
- CI run 36349473446 passed all repository checks and reached the native WSL2 checkout/host-check path; its final WSL2 result still needs confirmation after GitHub API rate limiting clears.
- Hermes may update its own runtime during a clean install; the smoke test records that host preparation separately from plugin results.
- A gateway restart is required after installation for the running gateway to load the plugin.
- Cross-profile plugin installation semantics and managed dependency recipes require verification on the minimum supported Hermes release.
- This plugin is not an OS sandbox; Hermes permissions remain the security boundary.
