# ADR-058 — Correlate API preparation with a committed ledger snapshot

Date: 2026-10-11. Status: implemented within the user-approved offline preflight task; P08 acceptance remains blocked.

## Problem

ApiPlan verifies frozen request bytes, destination, profile, and declared budgets but does not correlate those facts with current product storage. A valid standalone plan can refer to a missing, changed, started, or retired operation. The product currently has no registered live API context observer; local claims cannot establish genuine measurement or live provenance.

## Decision

`inspect_api_dispatch` in `src/consilium/shell/api_dispatch_preflight.py` validates the exact plan and then reads one committed SQLite snapshot. It requires the persisted intent, current debate revision, exact connection and connection revision, current round, PREPARED state, active wait gate, and no unresolved outstanding operation. It reuses ledger and admission checks instead of duplicating their transition rules.

A missing durable admission is reported as CONTEXT_ADMISSION_REQUIRED. Existing admissions must pass `require_current`; they still leave LIVE_OBSERVER_NOT_REGISTERED. No runtime registry currently supplies a live observer, and the report always has dispatch_allowed=false. It does not inspect credentials, contact a provider, reserve an attempt, advance a checkpoint, or confirm a response. Invalid inputs/conflicts produce fixed private error codes without retaining private exception context.

The report contains public identifiers, revision, operation hash, and a blocker. It is a historical preview, not a transferable capability or durable permit. An already open caller transaction is rejected to prevent inspection of uncommitted state. Future reservation must revalidate all conditions inside its write transaction, persisting intent before actual external dispatch. No current ledger guard or existing migration is changed.

## Validation

Fourteen new tests use real local SQLite storage. They cover matching preparation, reopening, changed bytes, claimed live admission, missing operation, bad revisions, replaced bindings, invoked/interrupted attempts, another outstanding operation, explicit wait, old-round storage, and a concurrent binding change after the first read. Snapshot tests demonstrate a consistent old revision during a concurrent write, then rejection on a fresh read; neither preview authorizes dispatch.

Most calls assert unchanged logical database contents and SQLite change counts and forbid credential/HTTPS access. The old-round and wait cases are explicit adversarial storage fixtures. The claimed live-observer case mocks local readers solely as a negative trust-boundary test; it is not evidence of a persisted live admission. A matching local fixture remains blocked, never LIVE_VERIFIED.

Actual source-bound command results and omissions are recorded in VALIDATION_REPORT.json and evidence/p08-api-preflight. Native checks already include the API suite; do not rerun covered suites merely for another report.

## Consequences and next task

This task supplies a checked API-to-ledger preflight boundary. Durable dispatch reservation and operation-bound result persistence remain subsequent approved work. Live calls remain user-deferred; no key is requested. The thirty protected requirements, canonical exit criteria, acceptance history, standing GitHub authorization, resume history, and evidence locations are preserved.
