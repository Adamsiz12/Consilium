# P05 council operation

`Council` uses the durable operation ledger, manual adoption, and official sources. Its path covers adopted architect questions, independent answers, analysis, user decisions, structured critique, targeted continuation, and an explicitly selected judge. A completed ordinary round enters WAITING_DECISION. The analyzer offers recommendations without authority to create a round.

Decisions are CONTINUE, CUSTOM, PAUSE, and FINISH. Finishing before complete peer critique is rejected. A later finish request enters WAITING_JUDGE_SELECTION; only user selection creates SYNTHESIS. The judge is a configured participant whose involvement, binding, and revision are recorded. Input preserves all earlier sources with aliases. Reports disclose judge involvement and bias mitigation, without guaranteeing impartiality.

Critiques identify full/partial acceptance or rejection with references/reasons. Scores are numeric 1–10 or explicitly NOT_SCORED. Incomplete critiques remain in attempt history without official sources or invented scores. Answer differences and objections retain identifiers/hashes; local deterministic analysis is not semantic judgment or truth probability. Judge output explicitly preserves uncertainty, unresolved issues, and dissent.

## Commands

Keep databases and debate exports outside source. `new` reads configuration containing `debate` (DebateSpec) and `bindings` (participant_id plus ConnectionSpec). Every participant needs exactly one binding. It does not adopt the question: stage an architect proposal through P04 and explicitly review it with `tools/review_architect.py`.

```sh
python tools/council.py --database /local/council.sqlite3 --debate-id UUID --revision 0 --exports /local/exports --actor LOCAL_USER --confirm-user-action new --config /local/config.json
python tools/council.py --database /local/council.sqlite3 --debate-id UUID status
python tools/council.py --database /local/council.sqlite3 --debate-id UUID --revision N --exports /local/exports --actor LOCAL_USER --confirm-user-action start --kind INDEPENDENT
```

Read the actual revision with `status` before each change. Use the same database/debate, current revision, export destination, actor, and explicit-action prefix for:

| Command | Effect |
|---|---|
| `mock-answer --participant-id UUID --response-file FILE` | Validated synthetic response on exact mock/mock-v1 binding |
| `manual-context --participant-id UUID` | Exact prompt/targets; later rounds need transfer confirmation |
| `seal` | Analyze a complete round and wait for a user decision |
| `decide --choice CONTINUE` | Permit a next round |
| `decide --choice CUSTOM --instruction TEXT` | Record custom continuation instructions |
| `start --kind REVIEW` | Begin authorized peer critique |
| `start --kind TARGETED --target TEXT` | Begin authorized targeted continuation |
| `decide --choice PAUSE` | Persist a pause |
| `resume-pause` | Return to decision selection without automatic continuation |
| `decide --choice FINISH` | Request judge selection after complete critique |
| `judge --participant-id UUID` | Explicitly select judge and begin synthesis |
| `finalize` | Atomically store that judge's valid result and completion |
| `export` | Reconstruct outputs from the database |

Use `tools/manual_answer.py` for initial manual answers and `tools/manual_round.py` for later rounds/judging. Save `manual-context` output for later `--context-file`. Explicit manual adoption does not verify external provider identity; synthetic manual tests do not prove external generation.

## Exports and recovery

Mutating commands produce checkpoint exports. The database remains operational authority: an export-write failure does not roll back a committed transaction. After failure, inspect `status` and retry only `export` to reconstruct output. Never resend because an export failed.

Each revision includes debate.json, debate.md, and participant histories. Completion adds final.md and evaluations derived from recorded positions/critiques, not fresh model judgment. EXPORT.json hashes files; LATEST.json is an atomic pointer. Existing differing generations are not overwritten. Model text uses fences longer than its own fences to preserve Markdown structure.

`recover` never sends automatically. Unknown attempts, incomplete output, and late prior-round results cannot complete a round. Ambiguous-operation manual continuation still needs explicit reconciliation. Tests cover genuine process termination around analysis, judge selection, and final commit.

P05 acceptance covers the internal council with local mock and manual paths. Live API/browser drivers belong to P08/P09; comprehensive recovery is P11. Real quality pilot scope is P06. P05 acceptance does not establish all thirty final V1 requirements.
