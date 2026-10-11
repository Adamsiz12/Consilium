# Development contract reference

Foundation contracts live in `src/consilium/core/contracts.py`; operation states and validation live in `src/consilium/core/operation_states.py`. Foundation acceptance was source-bound to native host evidence. Historical acceptance does not verify subsequent source changes.

| Data | Authority | Meaning |
|---|---|---|
| User requirement | `requirements/USER_CONSTRAINTS.yaml` in governance v1.3 | Thirty protected requirements; explicit user approval for changes |
| Recommendation / derived rule | Recommendation and rule registries in the same package | Distinct type and provenance; a recommendation cannot replace a requirement |
| Phase order / criteria | `ROADMAP.json` | Seventeen development phases, not a new requirement registry |
| Progress / continuation | `PROGRESS.json`, `resume` | Current phase, valid checkpoint, unfinished work, next action, quirks |
| Registered check | `CHECKS.json` | Command, test type, JUnit outputs, requirement mapping |
| Executed phase check | `evidence/runs/*/RUN.json` | Actual outcomes, source hashes, outputs; not automatic acceptance |
| Latest phase run | `evidence/latest/Pxx.json` | Path/hash of the latest completed recorded run, passing or failing |
| Phase review | Recorded `exit_evidence` file | Criteria, evidence, change impacts, open defects |
| Navigation | `evidence/navigation` | Derived output; freshness checks reject stale/manual versions |
| Transfer snapshot | `HANDOFF.json`, `MANIFEST.json` | Continuation snapshot, recorded execution state, transferred file hashes |
| Decision rationale | `docs/decisions` | Architecture reasoning and consequences, not the runtime operation ledger |

## Application contracts

P04 added `AdmissionBundle` with intent and independent-context evidence in additive V4 storage. `ContextSource`, `TransferGrant`, and `RoundContext` define later-round context. Use `docs/P04_COMPLETION_RUNBOOK_FA.md` for completed contract behavior; `docs/P04_CONTEXT_EVIDENCE_FA.md` preserves historical slices. Neither establishes live dispatch permission.

Contracts cover debates, participants, bindings, rounds, answers, critiques, user decisions, operation identity, frozen input, intent, capability, adapter requests/results, and delivery observations. Models are strict and immutable and reject extra fields. Generate schemas with `model_json_schema`. Public contracts have no password, key, cookie, or browser-profile fields.

`OperationIntent` is immutable intent in `PREPARED`; changes to attempts appear in `AttemptRecord`. SQLite and the operation ledger persist intent, dispatch start, results, and confirmation. `Delivery` and `ResponseState` remain separate: unknown delivery differs from confirmed delivery with an answer still pending. Observations bind to identifiers, connection revision, and input hash.

`CapabilityBinding` scopes capability to the exact connection revision; the structure itself cannot prove a claimed live verification. `ResumePlan` describes state and permitted action without authorizing automatic dispatch. `P02MockAnswer.v1` validates the limited offline answer; later artifact/council schemas have their own scope.

Logical operation, send attempt, and output generation have different identities. Matching content does not justify deleting a deliberately independent generation. State count follows the required semantics rather than a recommendation of a fixed number. Unknown delivery, delivered-but-pending, recorded result, and pending user/login decisions must remain distinguishable.

Adapters are needed from the beginning because MOCK, MANUAL, API, and BROWSER paths have different limits. Core behavior and result semantics are shared; delivery verification, request identifiers, conversation continuation, and cancellation capabilities are declared per connection. A missing capability cannot be replaced with a fabricated one.

Schema validation covers declared structure and constraints. Prohibiting completion without a judge and rejecting late results also require domain rules, revision checks, and runtime transactions. Do not derive every test from the implementation transition table: independently specified forbidden transitions and evidence help expose errors in that table.

Pure decision functions use explicit inputs, without hidden network, files, databases, clocks, or randomness. The shell obtains model answers and summaries; decisions over received text and explicit metadata can be pure. Pydantic was selected after evaluating validation needs and is pinned; ADR-003 records the rationale and limits.
