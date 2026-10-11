# ADR-059 — Atomic fail-closed API reservation boundary

Status: implemented offline boundary; successful durable live reservation remains blocked.

`reserve_api_dispatch` owns a BEGIN IMMEDIATE transaction. It verifies the exact
ApiPlan inside that transaction and reuses the same ledger correlation as the
read-only preview: current revision, exact intent and connection, round, prepared
state, active wait gate, outstanding operations, and current durable admission.
Caller-owned transactions are rejected without committing or rolling them back.

No trusted live observer is registered. Missing admission or a claimed live
observation therefore rejects the operation and rolls back; no SEND_STARTED,
reservation, credential access, or network request is produced. The function has
NoReturn, not a fabricated permit. Previews are never consumed as authorization.
This implements the atomic rejection boundary, not a successful durable dispatch
reservation. No schema migration or existing generic begin_send behavior changes.

Nine new tests cover rejection after reopen, repeated rejection, actual immediate
transaction and rollback, tampered plans, revision validation, stale snapshots,
concurrent binding changes, forged observation, and caller transaction ownership.
Synthetic observation fixtures are adversarial tests, not live acceptance evidence.
Initial test fixture failures (actor/reason and zero-based binding revision) and
an overly broad SQL trace assertion were corrected without weakening product guards.

Next work requires a separately designed registered observer provenance contract
before successful reservation can be implemented. That future path must persist
exact plan identity and the dispatch transition in one write transaction, recheck
all gates, and demonstrate concurrency/recovery semantics. It must not enable live
calls while the user's live-test deferral remains active. P08 remains BLOCKED.
