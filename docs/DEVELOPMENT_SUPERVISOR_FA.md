# Supervised development and recovery

```sh
python tools/qualityctl.py navigation
python tools/development_supervisor.py local
```

`local` performs development checks and configured current-phase checks; acceptance is separate. Use `check`, `native`, or `phase` for the required subset. Native and phase jobs are supervised. A blocked current phase remains blocked even when development checks pass.

## Time and process ownership

The default idle limit is 300 seconds without completed work, with a 900-second hard limit; individual tests have shorter bounds. Only a valid fresh milestone with the run nonce and ordered sequence refreshes progress. Ordinary output and heartbeats do not count as completed work.

Linux uses a dedicated process session. Windows starts an owned keeper inside a Job Object before the actual command; failed membership prevents execution. Termination covers owned descendants. These mechanisms are not a sandbox against malicious code or deliberate process escape.

## Recovery

Reconcile the exact run identity, source digest, successful receipt, and all artifact hashes, including the complete native report graph. If work finished before interruption and its complete receipt verifies, recover completion rather than execute it again. Incomplete safe local work may retry once; a failure or unresolved outcome stops the queue.

Each `evidence/development-supervisor` run retains state.json, current work, attempts, checkpoints, stop reasons, remaining work, and raw logs. After a chat interruption, inspect those receipts first and resume only genuinely incomplete authorized work. Do not replace prior accepted evidence.

The supervisor does not control ChatGPT, the GitHub connector, or the conversation's task queue. External publication is not a local check to replay. Independently inspect unknown external outcomes using PublicationGuard; never blindly resend.

Tests use short bounds to verify actual parent/child termination, recovery of fresh complete receipts, and rejection of stale/missing/hash-mismatched evidence. The command's normal five-minute default remains unchanged. Reuse valid work; new source, a failed run, stale evidence, or unresolved ambiguity justifies new execution.
