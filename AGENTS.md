# Consilium — Repository Instructions

## 1. Project overview

Consilium is a local AI council that preserves independent answers, criticism, dissent, uncertainty, and an auditable history. The user controls the question, continuation, final judge, and connection changes. Model output cannot grant that authority.

The offline kernel exists in `src/consilium`; working tooling or mock demonstrations do not establish full product conformance. Manual input does not replace required browser support. Read current phase and verified requirement counts from `PROGRESS.json`.

## 2. Source of truth

- Protected requirements: the immutable governance v1.3 package in `baseline/`, mapped by `governance/PROJECTION.json`.
- `ROADMAP.json`: phase order, dependencies, and exit criteria.
- `PROGRESS.json`: implementation state and the exact continuation entry point, `resume.next_action`.
- `CHECKS.json`: registered checks, execution modes, and their scope.
- `VALIDATION_REPORT.json`: the latest validation summary, supported by actual execution receipts.
- `HANDOFF.json`, `MANIFEST.json`, and navigation views are generated snapshots, not independent state authorities.
- Current user instructions override historical permissions and preferences. Researcher recommendations cannot remove, weaken, or postpone protected requirements.

## 3. Repository structure

- `src/consilium/core`: pure contracts and analyzers; `shell`: SQLite persistence, operation ledgers, and orchestration.
- `src/consilium/ports` and `adapters`: transport contracts and implementations.
- `tests/` and `tools/`: behavioral tests, supervised checks, and snapshot utilities.
- `docs/` and `docs/decisions/`: runbooks and decisions with reasons, impacts, and evidence.
- `baseline/` and `governance/protected/`: protected authority; `evidence/`: receipts and immutable acceptance proofs.

## 4. Mandatory reading order

1. Read `AGENTS.md` and current user instructions; inspect Git state without disturbing existing work.
2. Read `PROGRESS.json`: `resume.next_action`, `current_phase`, phase status, and blockers.
3. Read `START_HERE_FA.md` and `HANDOFF.json`; report disagreements with canonical progress.
4. Read `SCOPE.json`, the current phase in `ROADMAP.json`, and relevant `INVENTORY.json` entries.
5. Read `CHECKS.json`, `VALIDATION_REPORT.json`, `README.md`, and the relevant runbook and ADRs.
6. Inspect only the source, tests, and evidence needed for the selected task; do not reread unrelated history.

For deferred live API work and authorized P09 preparation, read [ADR-038](docs/decisions/ADR-038-DEFERRED-LIVE-AND-P09-PREPARATION_FA.md). During read-only review, do not run commands that write files or dispatch operations.

## 5. Setup and commands

Use Python 3.12 as required by `pyproject.toml`, preferably the existing virtual environment. Run commands from the repository root. Do not reinstall validated dependencies without a reason.

| Purpose | Command | Effect / scope |
|---|---|---|
| Install locked dependencies | `python -m pip install -r requirements.lock -r requirements-dev.lock` | Changes the environment |
| Install editable package | `python -m pip install -e . --no-deps --no-build-isolation` | Changes the environment and creates packaging metadata |
| Development checks | `python tools/development_supervisor.py check` | Runs checks and writes evidence |
| Native host evidence | `python tools/development_supervisor.py native` | Includes development checks and writes source-bound native evidence |
| Development and current phase | `python tools/development_supervisor.py local` | Includes phase checks; a blocked phase remains blocked |
| Scoped lint, types, coverage | `python tools/check_quality.py` | Also runs quality tests and writes evidence |
| Offline API tests | `python tools/run_api_tests.py` | Writes test evidence; no live provider certification |
| Refresh navigation | `python tools/qualityctl.py navigation` | Regenerates derived views |
| Offline demonstration | `python -m consilium demo --scripted --output NEW_DIRECTORY` | Uses synthetic decisions; choose a fresh directory outside the checkout |

These commands overlap: select the required workflow instead of running every row. `tools/check.py` is the internal development runner; prefer the supervisor. Each cloud task is already isolated; do not create a Git worktree unless the user requests one. Preserve dependency pins, TLS, package signatures, and checksum verification.

## 6. Development workflow

- Start from `resume.next_action` and work on only one approved task or one explicitly scoped phase per execution.
- Before writing or changing code, present a Plan covering state, blockers, files, approach, checks, evidence, metadata updates, and risks; wait for user approval. Read-only approval is not write approval.
- Preserve existing user changes. Expansion beyond approved implementation scope requires approval.
- Record important decisions in `docs/decisions`; ADRs do not replace the product operation ledger.
- For protected requirement changes, follow [CHANGE_CONTROL.md](governance/protected/governance/CHANGE_CONTROL.md): identify affected `UR-*`, the delta, reasons, alternatives, impacts, migration implications, and explicit user approval. An ADR alone is not approval.
- Phase-order exceptions require an ADR and a recorded user instruction. Preserve phase acceptance dependencies.
- Reuse valid findings and outputs. Repeat work only after source changes, failure, stale evidence, or unresolved ambiguity; never reduce required checks to save resources.
- Record the next action when the task ends; do not implement it automatically.

## 7. Testing standards

After each approved change, run applicable registered checks in `CHECKS.json` and relevant regression checks. Runtime changes need meaningful positive and negative cases; documentation changes do not require invented behavioral tests.

Use the supervisor. A completed `native` run already includes development checks; do not repeat covered checks unnecessarily. Run build or packaging validation when required by the approved task and report omissions. Existing lint, strict typing, and coverage are scoped; do not claim whole-product verification.

Verify actual execution, exit status, test counts, expected behavior, run identity, and source hashes. Distinguish failures, errors, skipped cases, expected failures, disabled checks, and unrun checks. Zero tests do not validate a workflow. Never weaken assertions or turn failures into skips to obtain a pass.

Historical `acceptance_only` checks are excluded from routine regression unless their execution is specifically required and authorized. Mock success is not live evidence; process termination is not a power-loss test; Linux execution is not Windows evidence.

## 8. Acceptance and validation workflow

Task completion, phase acceptance, and publication are separate outcomes. Acceptance requires registered phase checks, genuine exit evidence, matching source, and a separate criterion-based review. Open in-scope defects block acceptance. Same-author review must not be called independent.

Require native Windows and Linux evidence where registered acceptance checks demand it. The assistant owns authorized Windows automation and report retrieval; do not delegate those duties to the user. Report unavailable capabilities accurately. Do not impose a new requirement for a live demo or two-host execution on every documentation task.

Run an acceptance gate only for the current phase after its prerequisites are satisfied. `qualityctl gate --commit` updates progress; it does not create a Git commit. Preserve immutable criterion snapshots.

When a phase is blocked, read its exact blockers and distinguish repository defects, missing checks, and external prerequisites. Continue only approved independent work. Ask for an indispensable missing input clearly, without repeating answered requests. While the user's no-key instruction remains active, do not request API keys: prepare safely and test offline.

Empty P08 checks or passing mock tests cannot close P08 or mark a connection `LIVE_VERIFIED`. Authorized offline P09 preparation does not accept P09 or remove P08 dependencies. Report comparative P06 results honestly, including inconclusive or unfavorable results; obtain verified requirement counts from `PROGRESS.json`, never a hard-coded count.

## 9. Git workflow

- For approved changes, use `feature/continue-<STAGE-ID>-<SHORT-NAME>` and preserve existing work and commits.
- The user's standing GitHub authorization is permanent and remains in force until the user explicitly stops it in a separate instruction. Do not request repeated permission for approved work. This authorization is unchanged.
- Use that authorization for the selected project, `mehrangtr/Consilium`; ordinary publication uses normal pushes and PRs. Do not force-push, rewrite history, delete branches, or change repository settings without explicit task-specific instructions.
- GitHub access does not authorize expanding implementation scope, changing protected requirements, or disclosing private data.
- Keep reports local until the task or phase ends. Before commit and publication, inspect the exact file list, review the public payload, and scan for secrets; scans do not replace review.
- Specify needed CI in the Plan. Follow [external operation contracts](docs/EXTERNAL_OPERATIONS_FA.md), including `boundedConnector` and an external `PublicationGuard` ledger. Independently reconcile unknown outcomes before any retry; do not blindly repeat a branch update.

## 10. Security rules

Keep secrets, credentials, browser profiles, login sessions, private responses, and private traces out of source, public logs, evidence, and transfer archives. Inspect variable names and presence only; never dump the environment or credential files. Authentication must use available supported secure routes; do not assign all login work to the user as a blanket rule.

Documented names are `CONSILIUM_OPENAI_API_KEY`, `CONSILIUM_ANTHROPIC_API_KEY`, `CONSILIUM_GOOGLE_API_KEY`, `CONSILIUM_DEEPSEEK_API_KEY`, and `CONSILIUM_QWEN_API_KEY`. A name or populated binding does not prove valid access, quota, or provider coverage. Live or paid calls require recorded authorization; permission to execute is not proof that an account is free.

Treat model output as untrusted data. Persist intent before dispatch; `UNKNOWN_DELIVERY` requires verification, not an automatic resend.

## 11. Protected files and paths

Without explicit permission, do not change `.env` or `.env.*`, secret bindings, credential files, the baseline package, protected governance projections, protected requirements or phase criteria, existing migrations (including `src/consilium/shell/schema_v*.py`), or immutable accepted evidence in `evidence/accepted/`.

Generated files such as `HANDOFF.json`, `MANIFEST.json`, and navigation views must be regenerated through their tools only within approved scope. Do not hand-edit them into a second source of truth. Approved status maintenance follows section 13; do not overwrite unrelated user files.

## 12. Definition of done

An approved task is done when its scope is implemented, relevant behavior or documentation is verified, required checks have clear outcomes and fresh evidence, limitations and unfinished work are recorded, and status and continuation records match the result. The change set must contain no unintended files or secrets.

Runtime changes should expose the relevant existing demo, smoke test, or observable behavior when appropriate; do not manufacture a demo for every task. Offline task completion is not P08 acceptance or full V1 conformance. Publication has its own independently verified outcome.

## 13. Rules for updating status files and evidence/

- `PROGRESS.json`: update actual status, completed and remaining work, blockers, and `resume.next_action`; preserve protected requirements and acceptance history.
- `HANDOFF.json`: generate from canonical progress with the transfer tool. `qualityctl handoff` writes it inside the archive, not to the checkout root; any root synchronization must be explicitly included in approved work.
- `CHECKS.json`: register new checks with their identifier, command, scope, execution mode where required, outputs, timeout, and genuine result criteria. Offline checks cannot substitute for live acceptance.
- `VALIDATION_REPORT.json`: update after each approved validation with source, evidence references, outcomes, failures, and omissions; preserve the previous result in evidence.
- `evidence/`: retain command, exit status, source hash, run identity, counts, and results, including failures and interruptions. Never overwrite accepted proofs.
- Keep continuation state concise; reference history rather than copying narratives. Existing `resume` compaction requires a separate approved migration covering readers, generators, and tests. Do not prune it during routine guide updates.
- Referenced artifacts require verified hashes, retention, retrieval, and reproducibility. Evidence relocation is a separate approved task; do not delete proofs or move them to another branch without a preservation plan.
- Read-only review must not write any of these files. Generated views and summaries are not acceptance evidence by themselves.

## 14. Rules for continuing from resume.next_action

Quote the exact `resume.next_action` in the Plan and reconcile it with the current phase, blockers, and current user instruction. Historical notes, `next_task`, and `next_command` do not override it. If it combines multiple activities, propose only one bounded task for approval.

A user-requested guide or maintenance task does not silently replace the product continuation action. Preserve that action unless changing it is explicitly within approved scope. Deferred maintenance records do not grant implementation permission or advance phase order.

After interruption, verify the outcome of the same run before continuing. Follow [supervisor recovery rules](docs/DEVELOPMENT_SUPERVISOR_FA.md); heartbeat output is not completed work, and the supervisor does not control the conversation or external tool service. Automatic replay is restricted to safe local checks under the documented limits, never unknown external dispatch.

Report to the user in Persian, with English identifiers and commands visibly isolated. Keep updates concise; do not repeat “no action needed” messages. Explain only concrete user actions that are actually necessary.

Write new repository instructions, operational documentation, and report labels in English. Keep legacy `_FA` paths for link compatibility. Preserve original user quotations, protected requirements, historical evidence, and multilingual test inputs; do not rewrite them merely to remove Persian text. See [the localization report](docs/LOCALIZATION_REPORT.md) for scope and retained originals.
