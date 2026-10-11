# Initial manual answers with explicit adoption

This P04 path covers the first independent round. The question must already be explicitly adopted and the participant binding must be MANUAL. No external service is contacted; the path does not confirm a send or finish the debate.

Input includes answer text, actual prompt, declaration that the round was seen, and optional claimed provenance. Expected prompt is reconstructed from the adopted question and round contract. Input cannot set expected prompt or approval. Binding labels and author claims do not prove live origin. An adopted source remains MANUAL with unverified external provenance.

Stage the candidate without changing debate state. Review answer, both prompts, divergence, provenance, and hash. Adoption requires typing the exact hash/revision phrase. Other input, EOF, or a changed revision/binding rejects adoption.

```json
{
  "schema_version": 1,
  "candidate_id": "00000000-0000-0000-0000-000000000006",
  "debate_id": "00000000-0000-0000-0000-000000000001",
  "round_id": "00000000-0000-0000-0000-000000000004",
  "participant_id": "00000000-0000-0000-0000-000000000002",
  "actual_prompt": "exact prompt actually used; not a credential",
  "round_seen": true,
  "answer": "exact manual answer",
  "claimed_origin": "optional user claim, not verified evidence",
  "data_class": "PRIVATE"
}
```

Identifiers and revision below are samples. The database, round, and participant must exist; staging does not create them. Substitute actual identifiers/current revision and retain private input outside source.

```sh
python tools/manual_answer.py --database /local/path/debate.sqlite3 --revision 3 stage --submission /local/path/manual.json
python tools/manual_answer.py --database /local/path/debate.sqlite3 --revision 3 review --candidate-id 00000000-0000-0000-0000-000000000006
```

Adoption records source, event, and checkpoint in one transaction. Interruption before commit rolls them back; reopening after commit reconstructs the source. Additive migration V7 preserves previously published migration definitions and hashes.

Prompt mismatch or an unseen round records `DIVERGED`. Even when adopted, diverged content is exported without entering aligned later-round context. Alignment is not a transfer grant: privacy policy, budgets, and grants still apply. Existing unresolved operations cannot be concealed by manual replacement; use explicit reconciliation first.

Aligned adopted initial answers can satisfy round completeness. Unadopted or diverged answers cannot; unconfirmed operations still block the gate. A complete round still requires an explicit user decision to create the next round. Later-round context is recorded atomically with intent, official sources, grants, and budget; this does not convert manual content into live dispatch results.

See `docs/P04_MANUAL_ROUND_RUNBOOK_FA.md` for later answers/critiques and `enter` for multiline initial input. Reconciliation is now described in its dedicated runbook. Historical notes that P05 was unopened are superseded by current progress: P04 and P05 have recorded scoped acceptance. Live provenance and full V1 verification remain unresolved.
