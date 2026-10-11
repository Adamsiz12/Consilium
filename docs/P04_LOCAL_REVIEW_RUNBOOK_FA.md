# Local review of an architect proposal

This tool reviews a stored candidate without sending a model message. Its interface is tested automatically; these instructions do not ask the user to run checks now.

Keep an existing database outside source. Obtain the debate identifier, candidate hash, and current revision from that debate. The tool does not create a missing database.

```sh
python tools/review_architect.py --database /private/debate.sqlite3 --debate-id DEBATE_UUID --proposal-hash PROPOSAL_SHA256 --expected-revision REVISION_NUMBER
```

Before adoption, inspect the original question, proposal, every constraint, assumptions, and text differences. Only enter the complete displayed acceptance phrase if accepting. Other input or EOF does not adopt the candidate.

Acceptance binds to the exact hash and revision. A concurrent state change blocks the operation and requires fresh review. No keys, passwords, browser sessions, or general automatic-approval option are accepted.

For a focused check use `python tools/run_architect_tests.py`; the supervisor's full development workflow already includes it. Interface tests run a separate process with controlled input. Synthetic budget/grant tests do not claim provider measurements. Independent-input evidence is persisted with intent and verified when read; live dispatch and automatic continuation are not enabled by local adoption. See the completion runbook and preserved historical context notes for scope.
