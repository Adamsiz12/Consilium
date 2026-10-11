# Manual answer and critique input

The five planned services are ChatGPT, Claude, Gemini, DeepSeek, and Qwen. Live model identifiers remain unselected. A generic adapter interface does not establish implementation or live verification of each service.

A local user may enter externally obtained content through multiline CLI or a file. Origin remains MANUAL; claimed provider names are not live-generation evidence. No browser session or API key is needed. GUI text entry belongs to P12 and is not implemented here.

The debate/round must exist, the question must be explicitly adopted, and a local choice must establish a MANUAL participant binding. Entry creates no debate or binding. An unresolved earlier operation needs [explicit reconciliation](P04_MANUAL_RECONCILIATION_RUNBOOK_FA.md), preserving original delivery facts.

Use `tools/manual_answer.py` for initial answers and `tools/manual_round.py` for later answers/critiques. Substitute real current revisions/identifiers and keep personal data outside source.

```sh
python tools/manual_answer.py --database /local/debate.sqlite3 --revision 3 enter --candidate-id CANDIDATE_UUID --debate-id DEBATE_UUID --round-id ROUND_UUID --participant-id PARTICIPANT_UUID --actual-prompt-file /local/used-prompt.txt --round-seen
```

Entry stages, rather than adopts, a candidate. The displayed terminator contains its identifier. Spaces/blank lines are preserved. EOF before termination cancels incomplete input. File input also supports text containing the terminator. Use the relevant tool's `review` command for exact adoption.

Later-round context is built from official database sources. Local grants must cover all sources, destination, and current revision; model-written grants cannot approve themselves. Context and answer files remain separate and are both displayed before adoption.

```sh
python tools/manual_round.py --database /local/debate.sqlite3 --revision REVISION context --debate-id DEBATE_UUID --round-id ROUND_UUID --participant-id PARTICIPANT_UUID --grants /local/grants.json
python tools/manual_round.py --database /local/debate.sqlite3 --revision REVISION enter --context-file /local/context.json --candidate-id CANDIDATE_UUID --actual-prompt-file /local/used-prompt.txt --round-seen
python tools/manual_round.py --database /local/debate.sqlite3 --revision REVISION review --candidate-id CANDIDATE_UUID
```

Save `context` output to the designated local file. Obtain the prompt actually used from its real source. Missing round-seen confirmation or prompt mismatch creates DIVERGED content, retained in exports without filling context or the round-completion gate.

Later answers use plain text; critiques use structured input, for example:

```json
{
  "schema_version": 1,
  "critiques": [
    {
      "target_alias": "B",
      "points": [{"verdict": "REJECT", "reference": "claim", "reason": "explain disagreement"}],
      "score": 4,
      "scoring_reason": "reason for this score",
      "strengths": ["clear wording"],
      "weaknesses": ["missing evidence"]
    }
  ]
}
```

Use targets from actual local context, each exactly once. String/boolean numeric fields, duplicate/missing targets, and duplicate keys are rejected. Answer/author identities and rubric version come from local state, not model content.

`stage --context-file ... --submission ...` accepts files with only `schema_version`, `candidate_id`, `actual_prompt`, `round_seen`, `content`, and optional `claimed_origin`/`data_class`. Approval, expected prompt, and verified live-origin fields are forbidden.

Adoption binds to content hash/current revision. Other input, EOF, or changed revision/binding rejects it. Subsequent round creation requires a separate explicit user decision.

Adding a model to an existing provider usually needs identifier, capability, budget, and compatibility-test updates. A new provider needs an adapter and integration checks. Only capabilities outside existing contracts may require common-core changes. Earlier 6–12-hour API and 12–24-hour browser estimates are planning assumptions, not guarantees including access wait.
