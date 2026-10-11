# Project map and continuation handoff

Updated 2026-10-11. This document maps Consilium's implementation, authorities, evidence, and remaining work. PROGRESS.json is canonical. Historical acceptance, passing development checks, repository publication, and final product conformance are separate outcomes.

## Protected product scope

The local council preserves the original question, architect proposal, independent answers, peer critiques, disagreements, user decisions, and selected judge. A local database preserves operational and continuation state.

| Topic | Required scope |
|---|---|
| Providers | ChatGPT, Claude, Gemini, DeepSeek, Qwen |
| Connection paths | API, browser, manual |
| Target hosts | Windows, Linux |
| Protected requirements | Thirty, in immutable governance v1.3 |
| V1 phases | P00–P16 |
| Current call budget | Zero; live API tests deferred by the user |

Researcher recommendations cannot remove or weaken user requirements. Manual input does not replace browser support. Model content cannot authorize continuation, select the judge, or grant a transfer. The protected package and SCOPE.json define the scope.

## Authorities and repository structure

| File/path | Responsibility |
|---|---|
| AGENTS.md | Continuation instructions, authority limits, evidence preservation |
| START_HERE_FA.md | Entry guide, following AGENTS.md reading order |
| PROGRESS.json / resume | Phase status, gates, blockers, exact next action, checkpoint history |
| resume.english_documentation_update | This English-documentation maintenance record |
| ROADMAP.json | Phase order, dependencies, tasks, exit criteria |
| CHECKS.json | Registered acceptance commands; generic tests cannot substitute |
| SCOPE.json / INVENTORY.json | Scope and inventory with current evidence references |
| CONFORMANCE_MAP.yaml | Requirement-to-contract/implementation/test traceability |
| governance/PROJECTION.json | Byte verification against protected baseline |
| HANDOFF.json / MANIFEST.json | Generated transfer state and file hashes |
| TRANSFER_FILES.json | Explicit transferable source/evidence allowlist |
| evidence/navigation | Derived status/backlog, retaining original canonical text |
| docs/decisions | Architectural rationale, consequences, and limits |
| src/consilium/core | Pure contracts, question/context/analysis/observation logic |
| src/consilium/ports | Adapter and I/O boundaries |
| src/consilium/adapters | Protocol conversion, mock adapters, send/read preparation |
| src/consilium/shell | SQLite, ledgers, council orchestration, workers, journals |
| tests / tools | Behavioral/negative/recovery tests, supervision, validation, transfer |
| .github/workflows/check.yml | Native host automation and matrix validation |

Refresh generated views after canonical changes. Historical prose is not a second current-state authority. Accepted evidence is immutable. Operational intent precedes dispatch; raw and formal results remain distinct. Late/conflicting results cannot authorize a new operation. Read-only recovery does not resend unknown delivery. Operation, attempt, and export-generation identities remain separate.

## Accepted phase scope

| Phase | Recorded scope and limits |
|---|---|
| P00 | Established scope and honest inventory |
| P01 | Foundation/contracts with native evidence |
| P02 | Durable storage, migrations, dispatch/results, versioned decisions, real process-kill tests |
| P03 | Limited real browser feasibility within recorded conditions |
| P04 | Architect review, role contexts, independent-input preservation |
| P05 | Internal council using local mock/manual paths |
| P06 | Scoped functional acceptance; broader comparative evaluation incomplete |
| P07 | Stable participant exports, controlled recovery, recorded native visual checks |

These acceptances do not establish live integrations or final V1 conformance. All thirty final requirements remain unverified. PROGRESS.json records acceptance snapshot paths and hashes.

## P08 preparation and blockers

Offline codecs currently cover google and qwen. Request/observation contracts, explicit account/model binding, operation-bound results, incremental SSE, bounded owned workers, descendant cleanup, and conservative interrupted-prefix recovery exist. Local encrypted-transport and negative tests validate infrastructure, not provider accounts.

Relevant adapters include api_codec.py, api_plan.py, api_process.py, api_process_wire.py, api_process_progress.py, api_result.py, and sse_framer.py. The worker is `src/consilium/shell/api_process_worker.py`.

Trusted observations and durable product dispatch reservation are not fully connected to acceptance and the complete council path. Five-provider coverage, real account/model identity, quota, and response provenance remain unverified. CHECKS.json has no executable P08 acceptance registrations. User-deferred live API testing remains a separate external blocker; do not request keys or make live/paid calls under current instructions.

## Authorized P09 preparation

Durable observation journals, atomic raw capture, private errors without response echo, bounded saved-packet readers, and versioned receipts exist. Read-only CDP acquisition uses an owned worker. The attached browser is not owned by this worker and is not killed during cleanup.

Relevant shell modules include browser_watch_journal.py, browser_watch_ledger.py, qwen_capture_ingest.py, qwen_saved_read.py, qwen_saved_site_read.py, qwen_site_journal.py, and cdp_dom_read.py. See `docs/CDP_READ_ONLY_RUNBOOK_FA.md`.

Raw DOM text is not proof of response completion, real display, or independently observed account/conversation identity. Actual site selectors and trusted observation-to-product-ledger binding remain incomplete. ADR-038 permits offline preparation only, without accepting P09 or removing P08 prerequisites.

## Evidence interpretation

Read VALIDATION_REPORT.json for the latest completed task validation rather than copying changing test counts into static guides. Verify source digest, actual host, counts, run identity, and each referenced artifact hash.

| Evidence path | Meaning |
|---|---|
| evidence/accepted | Frozen accepted gate snapshots |
| evidence/targets | Native reports and per-host latest pointers |
| evidence/development-supervisor | Run-bound completion, interruption, failure, and recovery receipts |
| evidence/api-https-history | Local transport tests, not live provider/account evidence |
| evidence/p09 | Observation and saved-reader preparation |
| evidence/p06 | Real/incomplete pilot results with disclosed limits |
| evidence/english-documentation | Localization validation and preserved previous summary |

Same-author review in another pass is not independent. Development success does not accept a phase. Historical Windows evidence cannot verify changed source. Consult current CI separately and do not label queued work as passed.

## Continuation priorities

The exact approved entry point is PROGRESS.json.resume.next_action. Select one bounded task from it, present a Plan, and wait for implementation approval.

1. Bind trusted observations and durable dispatch reservation to request plans and operation-bound results; test interruption/restart before live activation.
2. Complete provider coverage and verified identities, quota, and response provenance without weakening the five-service scope.
3. Register P08 acceptance checks and execute genuine full-path evidence only after live-testing deferral is lifted.
4. Within the browser exception, bind actual selectors and independent site context to product operations.
5. Accept subsequent phases only through their prerequisites/current gate; P10–P16 retain roadmap order.

Earlier P08/P09 preparation estimates were 45–55 and 25–35 percent, with 20–35 remaining P08 engineering hours. These are planning estimates, not measured completion or logged time; external wait is unknown.

Resume compaction and evidence relocation remain deferred separately approved migration tasks, not part of this localization. Preserve existing history and accepted bytes.

## Publication and language

The public destination is mehrangtr/Consilium. The standing GitHub authorization remains unchanged until separately revoked. This task uses `feature/continue-P08-english-project-docs` and corrects the earlier branch-only publication gap by updating main too. Verify publication with independent ref/tree reads; merely creating a commit is insufficient.

Publish only reviewed public source, tests, guides, and evidence. Exclude keys, sessions, virtual environments, and private data. Publication does not accept P08. On reopening, inspect canonical progress and receipts before repeating past sends or pilots.

Operational guides/report labels are English. Legacy `_FA` filenames preserve links. Protected requirements, original quotes, historical ADRs/evidence, and multilingual input retain their source language. See `docs/LOCALIZATION_REPORT.md` and `docs/ARCHIVE_GUIDE.md` for the retained originals.
