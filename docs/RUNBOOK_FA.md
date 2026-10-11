# Development execution and continuation

Use Python 3.12. Git is required for tests that verify byte preservation through repository recording and extraction. Current offline checks do not incur model charges. Canonical progress and source-bound receipts determine current state and acceptance.

## Environment

Reuse a validated environment. Install development dependencies when a complete check is needed. From the repository root on Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-dev.lock
.venv/bin/python tools/qualityctl.py navigation
.venv/bin/python tools/development_supervisor.py check
```

On Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -r requirements-dev.lock
.\.venv\Scripts\python.exe tools/qualityctl.py navigation
.\.venv\Scripts\python.exe tools/development_supervisor.py check
```

These are reproduction instructions. The assistant owns authorized remote Windows execution and receipt retrieval.

## Checks and evidence

Choose the workflow needed; these commands overlap:

```sh
python tools/development_supervisor.py native
python tools/check_target_matrix.py
python tools/development_supervisor.py phase
```

`native` runs development suites and four CLI scenarios on the actual host, records environment and source identity, and refreshes mutable outputs while preserving immutable reports. Development checks include foundation, persistence, browser, architect/context, council, quality, pilot, and offline API tests. Persistence includes twelve genuine process-termination cases.

`check_target_matrix.py` requires valid passing Windows and Linux reports for the same source; missing, invalid, failed, or mismatched evidence blocks it. `phase` executes registered current/prior regression checks without accepting the phase. `local` combines development and phase checks; missing P08 acceptance checks leave the phase portion blocked.

Strict typing, lint, and coverage have explicitly limited scope; successful checks do not certify all source or all document rendering. Consult `CHECKS.json` and actual run receipts for authoritative commands and scope.

## Storage and recovery

`SQLiteStore` is in `src/consilium/shell/storage.py`. Store databases on a local disk outside the checkout. Each worker owns a connection; connections are not shared between threads. Durability uses WAL and `synchronous=FULL`. Process-kill tests do not establish resistance to power loss or hardware failure.

Migration V2 preserves V1 history and adds dispatch, result, and decision states. `store.ledger.begin_send` records state/events before external contact; `record_result` records the outcome transactionally. Validation and formal confirmation are separate. `DurableRunner` contacts adapters outside the transaction. Reading a prepared intent or resume classification is not permission to dispatch or retry.

`SENT` records attempt start and is ambiguous after interruption. `RESPONSE_PENDING` represents confirmed delivery with a pending answer. `CONFIRMED` requires positive validation and a formal answer. Unknown delivery cannot be automatically resent. A verified unsent retry requires an actor, reason, reliable non-delivery observation, and verified capability of that exact connection. An offline demonstration is not live capability evidence.

Logical operation, attempt, and output-generation identifiers remain distinct; matching content hashes do not establish operation identity.

## Durable offline demonstration

Use a new database outside the checkout:

```sh
python tools/run_consilium.py durable-mock --database ../local-demo.sqlite3 --question "offline question"
python tools/run_consilium.py resume --database ../local-demo.sqlite3 --debate-id DEBATE_UUID_FROM_OUTPUT
```

The first command exercises synthetic dispatch, confirmation, and database reopening. Substitute its actual debate identifier in the second command. `resume` reads state and makes no model call. Existing demonstration databases are rejected. `--mode BROWSER --scenario timeout_after_send` simulates ambiguity; it is not a real browser test.

The V2 kernel export contains intents, attempts, formal results, quarantine, decisions, bindings, and resume state. Its `debate_completed` remains false; use the later council/export path for council completion rather than treating this kernel demonstration as a finished debate.

Backups use SQLite's backup API and a new destination. Do not copy an active database as a raw file. Ordinary failures close the destination and remove incomplete output. A backup is valid only after successful return and integrity checks. Automatic restore and scheduled backup are not established by this path.

## Acceptance

Start from `PROGRESS.json.resume.next_action`. An open in-scope defect blocks acceptance. Only gate the current phase with satisfied prerequisites, real registered evidence, and a criterion-based review. The following is a historical P02 example, not a command to run at current P08:

```sh
python tools/qualityctl.py review-template P02 --out evidence/reviews/P02-final.json
python tools/qualityctl.py gate P02 --receipt evidence/runs/ACTUAL_RUN/RUN.json --review evidence/reviews/P02-final.json --commit
```

Use real paths. `--commit` updates progress, not Git. Do not rerun an already accepted phase gate; preserve its immutable snapshot. P03 browser feasibility follows P02 historically; current continuation is governed by current progress and ADR-038.

## Transfer

```sh
python tools/qualityctl.py navigation
python tools/qualityctl.py handoff --out ../Consilium_Handoff_NEW.zip
python tools/qualityctl.py verify ../Consilium_Handoff_NEW.zip
```

Choose a new archive destination. Register required source/history in `TRANSFER_FILES.json`. Transfers include accepted proofs and the latest failure where recorded; acceptance criteria are frozen at the gate. For a reproduction exercise, extract into a fresh directory and run the applicable checks: hash verification alone is not execution. Do not overwrite immutable evidence or private files.
