# Sprint 7 decision log

Revision 2. Decisions below guide implementation; they are not evidence that the features are complete.

## D-01 — Fix local contract failures before host certification

The recorded host inventory reports a missing dependency. Local scheduler and acceptance invariants can be tested independently and define this sprint boundary. Host repair and certification remain in Sprint 6; capability claims require a refreshed inventory and real receipts.

## D-02 — Queue is not execution

Creating a durable graph does not authorize worker capacity. Only runnable tasks reserve capacity; native task creation must be deferred or proven non-runnable by the host contract.

## D-03 — Evidence must describe the requested change

An empty file list and a successful no-op command do not prove implementation. No-change outcomes require an explicit spec declaration and separate evidence.

## D-04 — Preserve task IDs and separate inheritance from dependencies

Retain S7-01–06. S6-04–05 and S6-07–08 identify work being carried forward, not unfinished prerequisites for that same work. S7-01 and S7-03 may proceed independently, coordinating shared schema changes. Diagnostics depend on both completed implementation paths.

## D-05 — Finalize contracts before engineer admission

Requirements/architecture tasks can refine a draft, but engineer admission requires a finalized criterion/check contract. Worker-declared checks may add coverage; they cannot reduce the authoritative contract. Revision invalidates affected evidence and review. Passing arbitrary commands is not semantic proof of a requirement.

## D-06 — Use explicit verdicts and outcomes

Approval is a structured reviewer decision bound to current implementation and spec. Missing legacy verdicts require resubmission. `no_change_needed` is separately evidenced and reported; it is not a general exception for empty submissions. The initial scope adapter uses Git; unsupported repositories receive an explicit blocker.

## D-07 — Commit completion and its scheduling wake-up together

Use durable receipt reduction and a persisted wake-up/outbox so a crash cannot lose eligible children. External dispatch follows committed intent. A duplicate receipt has no additional effect; unknown outcomes keep conservative reservations. The exact callback/polling mechanism is deferred to the verified host adapter.

## D-08 — Migrate conservatively

Choose the schema increment during implementation and test the actual v6-to-new migration. Preserve IDs, evidence, and resource counters; use upgrade blockers for missing contract/receipt/verdict facts. Never manufacture successful historical evidence. Retain v5 migration coverage.

## Open integration questions

| Question | Owner / resolution gate |
| --- | --- |
| Which host response provides stable attempt identity and trustworthy elapsed runtime? | S6-01/S6-11 native contract; S7-02 defines a normalized local adapter interface meanwhile |
| Can native card creation remain non-runnable until explicit admission? | Native certification gate; S7-01 defaults to deferred creation |
| Which supported host callback or poller wakes the coordinator after completion? | Native integration gate; S7-02 proves durable local wake-up/recovery semantics |
| Which physical record layout/schema increment best extends the current v6 ledger? | S7-01/S7-03 implementation review with populated migration tests |

These questions do not waive local requirements. Unsupported native behavior stays gated rather than inferred from simulator success.
