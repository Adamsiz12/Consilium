# Consilium — Extended guide

Consilium is a local council of multiple models with durable state and explicit user control. The protected scope contains thirty requirements and seventeen development phases.

P00–P07 are accepted within their recorded scopes. P08 is blocked; offline P09 preparation has a recorded user exception. Read [current status](docs/CURRENT_STATUS_FA.md), the [continuation map](docs/PROJECT_CONTINUATION_MASTER_FA.md), and canonical `PROGRESS.json` before continuing.

Preparation includes request/result contracts, incremental SSE framing, bounded owned worker processes, partial-response recovery, exact operation-result binding, durable browser observation journals, saved packet readers, and read-only page acquisition. These modules do not establish complete live integrations for five providers. Live API testing remains deferred by the user; broader P06 comparative evaluation is incomplete.

The persistence kernel stores dispatch intent, attempt start, results, formal confirmation, versioned decisions, and recovery without automatic resend. Acceptance snapshots and native results must be interpreted within their recorded scope and source hashes. This is not a complete V1 product.

Read `AGENTS.md`, `PROGRESS.json`, `START_HERE_FA.md`, and `HANDOFF.json` in the mandatory order. Reproduction commands are in `docs/RUNBOOK_FA.md`. A passing execution does not automatically accept a phase.

```sh
python tools/qualityctl.py navigation
python tools/development_supervisor.py check
python tools/run_consilium.py mock --question "offline question"
python tools/run_consilium.py durable-mock --database ../local-demo.sqlite3 --question "offline question"
```

Use Python 3.12 and pinned dependencies. Offline checks need no provider account or API key. The assistant runs authorized Windows automation and retrieves the results; these commands do not assign that work to the user.

`check` runs supervised development checks. `native` also records evidence for its actual host. `local` attempts current phase checks as well; P08 acceptance remains blocked until registered checks and real evidence exist. Cross-host evidence must match the same source digest.

Preserve accepted evidence in `evidence/accepted/`. Passing foundation or persistence checks does not prove all thirty requirements, council quality, or live connectivity.

`docs/P04_COMPLETION_RUNBOOK_FA.md` describes architect review, independent/critique/targeted/judge context, manual provenance, budgets, and history. The following optional recorder produces before/after questions, role inputs, and local recovery evidence using synthetic data without live calls:

```sh
python tools/record_p04_context_examples.py
```

See [P05 council operation](docs/P05_COUNCIL_RUNBOOK_FA.md) for stop, continue, judge selection, and exports. Read actual acceptance and source-bound receipts rather than inferring phase completion from a demonstration.

This guide is English. Its `_FA` filename is retained for existing links. [Localization scope](docs/LOCALIZATION_REPORT.md) explains why original requirements, user quotations, test data, and historical evidence retain their original language.
