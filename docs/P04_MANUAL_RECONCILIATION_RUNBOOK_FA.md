# Manual continuation after an unresolved operation

This path applies to an existing debate/current round and a participant with an unresolved operation. Manual selection does not change prior delivery facts, contact a service, or resend. A complete received or confirmed answer cannot be replaced.

Create a fresh manual-binding specification outside the checkout. A claimed service/model is not verified provenance:

```json
{
  "connection_id": "00000000-0000-0000-0000-000000000950",
  "provider_id": "claimed-service",
  "model_id": "unverified-model",
  "mode": "MANUAL",
  "account_binding_id": null
}
```

Use a genuinely fresh identifier, not this sample. Keep databases, bindings, and private content outside source.

```sh
python tools/reconcile_manual.py --database ../state.sqlite3 --revision CURRENT_REVISION --debate-id DEBATE_UUID --round-id ROUND_UUID --participant-id PARTICIPANT_UUID --manual-connection-file ../manual-connection.json
```

The interface shows binding details, every earlier attempt, and selection consequences. Only the exact phrase containing current hash/revision followed by a nonempty reason records manual continuation. EOF, generic approval, stale hash, or a concurrent change cannot do so.

After recording, use the new revision. Use `tools/manual_answer.py` for initial answers and `tools/manual_round.py` for later answers/critiques. Rebuild later-round context and transfer grants for the new binding/revision; old context is invalid. Manual content adoption remains a separate explicit action. Diverged content is retained without completing the round.

Exports include `manual_operation_reconciliations` and untouched attempt history. `UNKNOWN_DELIVERY` remains unknown. Late results enter `rejected_results` with `MANUALLY_RECONCILED_OPERATION`. This record is neither dispatch authority nor live-origin evidence.

The operation is rejected if the waiting gate belongs to another action or a complete answer already exists. Do not delete records or manually repair attempt states. Record remaining work in canonical progress. GUI text entry remains P12 scope.
