# Reproducing P04 context contracts

Canonical progress and immutable `evidence/accepted/` snapshots determine phase acceptance. This runbook explains context checks; a passing example is not full V1 acceptance or live model verification.

```sh
python tools/qualityctl.py navigation
python tools/development_supervisor.py check
python tools/record_p04_context_examples.py
python tools/qualityctl.py status
```

The optional recorder writes `evidence/p04/context-examples/RUN.json`. It exposes before/after questions, exact constraints, assumptions/provenance, round inputs, preserved dissent, synthetic model measurement, and database reopening. It uses a temporary database, removed after connections close, with no account, key, or network call. Do not run it solely to regenerate historical evidence during documentation maintenance.

Existing tools preserve genuine user input for architect adoption, initial manual answers, manual critiques, and prior-operation reconciliation:

```sh
python tools/review_architect.py --help
python tools/manual_round.py --help
python tools/reconcile_manual.py --help
```

A future connection must first implement the destination contract and that model's capability. Model content cannot authorize continuation, transfer consent, judge selection, or a registered observer. `observe_context` accepts only the registered offline observer. Synthetic token measurement cannot be generalized to a live provider. Reading a stored receipt grants neither send nor retry permission.

ADR-025 describes the observation boundary. `test_context_observers.py` and `test_context_history_observer.py` cover observation/history; earlier architect, round, source, and manual-input tests remain part of full checks. Do not repeat accepted phases or past feasibility sends without a new authorized reason.

`build_architect_request` freezes the original question, all constraints, and exact output schema. `stage_architect_response` strictly parses output, rejecting duplicate keys, constraint changes, and self-approval. It creates only a candidate. Local explicit review/adoption is required before the first round. Live architect dispatch belongs to later integration work.
