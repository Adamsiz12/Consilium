# Consilium

A local AI council that keeps the user in charge of the question, continuation,
and final judge. It preserves independent answers, peer criticism, dissent,
uncertainty, and an auditable history.

The implementation has a durable SQLite council kernel, a manual input
pipeline, stable participant exports, and preparatory API and browser modules.
P00–P07 are accepted within their recorded scopes. P08 is the current blocked
phase; P09 has user-authorized offline preparation. Live integrations for
ChatGPT, Claude, Gemini, DeepSeek, and Qwen remain required for V1. Manual input
does not replace browser support.

## Try the offline demonstration

Use Python 3.12 in a virtual environment:

```sh
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps --no-build-isolation
python -m consilium demo --scripted
```

`--scripted` explicitly selects synthetic, prewritten demonstration decisions.
For interactive decisions, run `python -m consilium demo` in a terminal.
The demo makes zero live or paid calls. It prints its output directory,
exports versioned Markdown and JSON, preserves objections, and checks that
reopening the database reproduces the final state. `--output NEW_DIRECTORY`
chooses a destination and refuses an existing directory.

## Architecture and reliability

Pure contracts and analyzers live in `src/consilium/core`. SQLite persistence
and orchestration live in `src/consilium/shell`; transport contracts are in
`src/consilium/ports`. Council SQL is encapsulated by `SQLiteCouncilRepository`.
The operation ledger records intent before dispatch. `UNKNOWN_DELIVERY`
requires verification rather than a blind resend. Model text cannot authorize
a round, select a judge, or grant a transfer. Consensus is not a truth probability.

Tests include genuine subprocess termination, migration rollback, stale
revision rejection, exact replay, and bounded generated event sequences.
New review inputs have persisted, balanced aliases and a versioned rubric.
Optional critique spans bind to exact UTF-8 answer bytes and quote hashes.

## Current state and evidence

`PROGRESS.json` is the canonical phase and continuation record; `HANDOFF.json`
and `evidence/navigation` are derived from it. See
[current status](docs/CURRENT_STATUS_FA.md) and
[project continuation map](docs/PROJECT_CONTINUATION_MASTER_FA.md) for the
implementation, evidence, remaining work, and publication records.

P06 has a scoped functional acceptance and real recorded pilot material; the
broader comparative evaluation remains incomplete. P07 includes stable exports,
controlled recovery, and recorded native visual checks. P08 preparation includes
incremental SSE framing, bounded owned HTTPS workers, partial-response recovery,
and exact result binding. Browser preparation includes durable observation
journals, saved Qwen packet readers, and read-only CDP acquisition. These modules
do not establish a complete live provider integration. Live API testing remains
deferred by the user. Mock test success does not establish model quality or full
V1 conformance, and all thirty final V1 requirements remain unverified.

`CONFORMANCE_MAP.yaml` traces all thirty protected requirements across
protection, contract, implementation, and final verification. Its JSON syntax
is valid YAML. Run `python tools/check_conformance.py` to verify references and
generate `evidence/conformance/DASHBOARD.md`. The immutable baseline package
remains the authority; direct protected projections are byte-checked.

## Development checks

```sh
python -m pip install -r requirements.lock -r requirements-dev.lock
python tools/qualityctl.py navigation
python tools/development_supervisor.py check
```

`check` verifies the implementation without attempting phase acceptance. Use
`native` to record source-bound checks for the current operating system. `local`
also attempts the current phase checks; P08 remains blocked until its acceptance
checks and evidence exist. Native GitHub Actions results are checked separately
for Windows and Linux, and historical runs cannot verify a changed source.

The five-minute supervisor watches completed work, not heartbeat output. Checks
have bounded timeouts and measured durations. Strict type checking and coverage
are currently scoped to three new reliability modules, not the whole product.
Native Windows and Linux reports must match the actual source digest. Security
advisory checks require network access; a timeout remains unverified.

Operational guides are written in English; legacy `_FA` filenames remain for
link compatibility. Original requirements, quotations, and historical evidence
retain their source language; see [localization scope](docs/LOCALIZATION_REPORT.md).

See [extended guide](README_FA.md), [contribution guide](CONTRIBUTING.md),
[security reporting](SECURITY.md), and [licensing status](LICENSING.md).
