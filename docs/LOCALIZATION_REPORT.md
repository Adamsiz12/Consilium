# English documentation change report

## Reason and scope

Earlier English AGENTS.md commits were published on feature branches, while main retained the Persian guide. This task publishes the approved English guide and useful operational-documentation translations to main and the task branch, verified by independent Git reads. It does not advance product phases.

## Changes

- English repository instructions and language policy, extended README, entry guide, handoff template, and operational runbooks.
- Corrected outdated instructions that implied repeated suites, obsolete unopened phases, or whole-project type verification.
- English fixed labels in qualityctl navigation; original canonical tasks, criteria, quotations, keys, and paths are preserved.
- One regression test checks English headings and canonical-input byte preservation with a Persian continuation fixture.
- Equivalent English translations of the current next action, P08 blockers, informational scope/inventory prose, and the two deferred maintenance task descriptions. Legacy *_fa keys remain compatible.
- Regenerated navigation, HANDOFF.json, and MANIFEST.json using existing tools; updated validation and progress summaries with actual outcomes.

## English guides

- [AGENTS.md](../AGENTS.md)
- [HANDOFF_TEMPLATE_FA.md](../HANDOFF_TEMPLATE_FA.md)
- [README.md](../README.md)
- [README_FA.md](../README_FA.md)
- [START_HERE_FA.md](../START_HERE_FA.md)
- [docs/AUTOMATED_WINDOWS_FA.md](AUTOMATED_WINDOWS_FA.md)
- [docs/CDP_READ_ONLY_RUNBOOK_FA.md](CDP_READ_ONLY_RUNBOOK_FA.md)
- [docs/CURRENT_STATUS_FA.md](CURRENT_STATUS_FA.md)
- [docs/DATA_CONTRACTS_FA.md](DATA_CONTRACTS_FA.md)
- [docs/DEVELOPMENT_SUPERVISOR_FA.md](DEVELOPMENT_SUPERVISOR_FA.md)
- [docs/EXTERNAL_OPERATIONS_FA.md](EXTERNAL_OPERATIONS_FA.md)
- [docs/MODEL_EVALUATION_PLAN_FA.md](MODEL_EVALUATION_PLAN_FA.md)
- [docs/P03_PROBE_RUNBOOK_FA.md](P03_PROBE_RUNBOOK_FA.md)
- [docs/P04_COMPLETION_RUNBOOK_FA.md](P04_COMPLETION_RUNBOOK_FA.md)
- [docs/P04_LOCAL_REVIEW_RUNBOOK_FA.md](P04_LOCAL_REVIEW_RUNBOOK_FA.md)
- [docs/P04_MANUAL_RECONCILIATION_RUNBOOK_FA.md](P04_MANUAL_RECONCILIATION_RUNBOOK_FA.md)
- [docs/P04_MANUAL_ROUND_RUNBOOK_FA.md](P04_MANUAL_ROUND_RUNBOOK_FA.md)
- [docs/P04_MANUAL_SOURCE_RUNBOOK_FA.md](P04_MANUAL_SOURCE_RUNBOOK_FA.md)
- [docs/P05_COUNCIL_RUNBOOK_FA.md](P05_COUNCIL_RUNBOOK_FA.md)
- [docs/P07_OUTPUT_RUNBOOK_FA.md](P07_OUTPUT_RUNBOOK_FA.md)
- [docs/PROJECT_CONTINUATION_MASTER_FA.md](PROJECT_CONTINUATION_MASTER_FA.md)
- [docs/REPOSITORY_SYNC_STATUS_FA.md](REPOSITORY_SYNC_STATUS_FA.md)
- [docs/RUNBOOK_FA.md](RUNBOOK_FA.md)
- [docs/SCOPE_AND_INVENTORY_FA.md](SCOPE_AND_INVENTORY_FA.md)
- [docs/p06/RUNBOOK_FA.md](p06/RUNBOOK_FA.md)

See [the archive guide](ARCHIVE_GUIDE.md) for preserved original-language material. Legacy `_FA` filenames are retained to avoid breaking paths; no file is renamed.

## Deliberately retained originals

Immutable baseline/governance, ROADMAP.json criteria, historical ADRs/research/checkpoints, acceptance and historical evidence, original user quotes/authorization objects, and multilingual fixtures/model text retain their source language. Derived reports can include those original strings while their labels are English. This task does not claim every repository byte is English.

Existing resume data is not compacted. Existing evidence is neither moved nor deleted. MAINT-RESUME-COMPACTION and MAINT-EVIDENCE-RETENTION remain deferred separate tasks. Permanent GitHub authorization remains exactly unchanged.

## Validation and outcome

Actual commands, source digest, results, counts, omissions, preserved-data checks, and evidence references are recorded in [the validation summary](../evidence/english-documentation/20261011/RUN.json) and root VALIDATION_REPORT.json. Checks include one supervised native development run, the current-phase blocked-state check, focused tool lint, wheel packaging, navigation freshness, secret scanning, and transfer verification. Reuse the native run for covered suites rather than rerunning them.

P08 remains BLOCKED. Live API tests remain USER_DEFERRED_NO_KEY_REQUEST. No live or paid provider call is made. Windows/CI status must be read separately from local Linux results; publication is independently verified in the final completion report.
