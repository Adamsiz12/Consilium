# P06 quality pilot

`PREREGISTRATION.json` fixes eight problems and three methods with equal call, output, time, and cost ceilings. Actual consumption is recorded separately. Each method shares one architect call. Single-model uses one final answer; the other methods use two independent answers, two critiques, and one synthesis. The council judge requires explicit selection.

Use existing product paths for real manual answers. Manual-origin confirmation does not verify provider identity. Retain exact prompts/answers privately outside source; the tool verifies hashes and budgets:

```sh
python tools/p06_pilot.py status --workspace /absolute/private/pilot
python tools/p06_pilot.py prepare --workspace /absolute/private/pilot
python tools/p06_pilot.py import --workspace /absolute/private/pilot --record observation.json --prompt prompt.txt --response response.txt --confirmed-manual-origin
python tools/p06_pilot.py blind --workspace /absolute/private/pilot
python tools/p06_pilot.py score --workspace /absolute/private/pilot --scores completed-scores.json
```

Each observation records unique identifier, task, method, claimed provider, prompt/answer hashes, observed duration, zero cost, known token counts or null, and final-output flag. Origin is MANUAL and automatic external-identity verification is false. Synthetic fixtures test tooling without establishing model quality.

## Ledger and budgets

Observation storage uses atomic SQLite; concurrent importers cannot delete one another's records, and interruption before commit preserves earlier data. Legacy CALLS.json is migrated only after text-hash verification, preserving its original bytes. Method stage order and per-call ceilings are checked. Single-model and single-model iteration retain the selected model; council independent answers require two models, not merely a different judge.

The shared architect prompt/answer is identical across all three methods for each problem. Observations share the genuine `shared_architect_call_id` but each has a unique `call_id`. Its share counts in every method budget; aggregate physical call/time totals count it once. A legacy ledger without this linkage is not ready for evaluation.

`prepare` extracts problem text without reference answers. Blinding requires all 24 outputs and intermediate calls. Unknown token counts do not prove full actual-consumption compliance. `outcome` is SUCCESS, FAILED, or UNKNOWN; the latter two require `failure_reason` and are not final outputs. Preserve exact error bytes or an empty no-response file with its hash.

A repair links through `repair_of` only to the last definite failure of the same stage/model. Unknown delivery does not permit resend. Failure and repair consume the original budget. A six-stage method with a failure cannot also repair and finish within six calls; it remains incomplete. Do not increase budget or delete failure to obtain completion.

```sh
python tools/run_pilot_tests.py
python tools/check_p06.py preflight
python tools/check_p06.py evidence
```

The broader evidence check remains an explicit barrier until real product-path review, blinded scoring, findings, and re-estimation exist. `CONSILIUM_P06_WORKSPACE` locates a private ledger and grants no dispatch permission. P06's separately recorded functional acceptance does not claim this broader comparison passed; P07 has subsequently been accepted within its scope.

## Blinding and scoring

Blinding atomically fixes four private files: BLINDED.json, PRIVATE_BLIND_MAP.json, SCORING_TEMPLATE.json, and JUDGE_REFERENCES.json. The blinded packet excludes method/model identity; do not give its private map to the evaluator. References are separate and supplied only after answer generation. Packet identity binds all observation hashes, plan revision, and rubric. Interrupted generation can finish the same bytes without overwriting; the ledger accepts no new observations after blinding.

Copy the scoring template. Declare evaluator name, HUMAN_MANUAL or MODEL_MANUAL origin, and SAME_AUTHOR or DECLARED_OTHER_EVALUATOR relationship. Every `p06-quality.v1` dimension needs a score of 1–10 and reference-based reason. Fixed weights are evidence 0.40, reasoning 0.25, constraint preservation 0.20, and coverage 0.15.

Incomplete/invalid/duplicate scores, changed answers, and missing reasons are rejected. Source scores and report are frozen together; existing scores cannot be replaced. Reports show paired task differences and observed ranges; this small sample cannot establish general superiority. Evaluator identity/independence remain manually declared. Scores are not truth probabilities, and style can reveal model identity.

Disclose login wait, format-repair calls, and exhausted quotas. Earlier engineering time was not measured and estimates cannot become actual hours. A full comparative completion claim requires all methods' real outputs, blind scores, control-error review, and documented re-estimation; it cannot be inferred from scoped functional acceptance.
