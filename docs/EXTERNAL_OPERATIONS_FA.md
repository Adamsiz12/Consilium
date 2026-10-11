# Bounded external operations and publication reconciliation

`boundedConnector` in `tools/connector_wait.js` defaults to a 25000-ms wait ceiling. Load and invoke it in the tool runtime. Timeout returns UNKNOWN_WAIT_TIMEOUT; connector errors remain unknown without echoing private error content. It does not cancel the external service or restart the conversation. A late operation may still take effect.

Before Git publication, persist the plan and attempt permit with PublicationGuard in `tools/publication_guard.py`. Keep its SQLite database outside source and public transfers. Plans contain operation kind, public resource name, request hash, project source digest, and expected Git identity, not file bodies, secrets, or private responses. Structural validation is not a universal secret detector; resource names must be public.

1. `prepare` the plan and inspect any prior state. Do not write an already completed operation again.
2. `begin` a fresh attempt permit and honor its deadline/nonce.
3. Make one external call; a success response must match the expected identity.
4. On timeout/error, preserve uncertainty with `unknown`. A leftover attempt after interruption becomes SESSION_INTERRUPTED.
5. Independently read actual object/ref state and `reconcile`. An unknown read is not evidence of absence.
6. Only a precomputed immutable Git blob/tree/commit may receive one additional attempt after explicit absence proof. A new branch-update plan for the same resource is blocked while its earlier uncertainty remains unresolved.

```sh
python tools/publication_guard.py --database /local/path/publication.sqlite3 pending
```

Other commands accept a JSON object on stdin; the database parent directory must already exist. Product dispatch, model messages, PR creation, and repository merging do not inherit immutable-object retry. Reconcile their unknown outcomes separately. The ledger, deadline, and process supervisor limit waits/repetition without independently controlling the conversation.

Ledger tests cover reopening, concurrent controllers, ambiguity, old-attempt late replies, ref updates, fresh-plan bypass, bounded attempts, and private input rejection. The recorded five JavaScript wait-helper tests used simulated connectors in an actual JS runtime; they do not prove external-service cancellation.

For server-created commits whose author/time metadata prevents advance prediction, SERVER_COMMIT records expected tree SHA and a request hash covering tree_sha, ordered parent_shas, and message_sha256. It allows one attempt, without immutable-object retry. After independent object retrieval, `reconcile_commit` verifies actual commit identity, tree, parent order, and message hash. Ordinary identity-only reconciliation is forbidden for this operation. Unknown/mismatched results do not authorize retry; update a ref only after the commit is fully verified.
