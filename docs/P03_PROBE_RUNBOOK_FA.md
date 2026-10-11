# Bounded browser feasibility probe

A real positive connection path was examined with manually authorized login. Read current results and permissions from `PROGRESS.json.resume`; historical refusals and login waits are not current state. This runbook grants no new login permission and makes no full-capability claim.

## Prerequisites and recording

After a genuinely authorized session, observe the account, model, and exact conversation and bind them to non-secret local identifiers. Store sanitized observation evidence outside the checkout and record its hash. Do not include token-bearing URLs, cookies, passwords, or session data. Use contracts from `core/browser_probe.py`; sample fixture values are not service evidence.

With `SQLiteStore`, prepare an existing test debate, round, browser binding with an account identifier, and one-message intent. Use `BrowserBinding.content_hash` as `AdapterRequest.transport_binding_hash`. The request budget is at most sixty seconds. Convert request, binding, and valid session observation into a `ProbeTicket`. The tool does not create accounts or debates automatically.

Before freezing the prompt, add a fresh attempt marker. The observed user message must include that exact marker so an older similar question cannot prove a new send:

```text
[consilium-probe:<attempt_id>]
```

Keep inputs and receipts outside source. Substitute the actual database revision; these numbers are illustrative:

```sh
python tools/run_browser_probe.py start --database /private/probe.sqlite3 --ticket /private/ticket.json --input /private/plan.json --current-context /private/current-context.json --expected-revision 3
```

Immediately before start, separately observe account/model/conversation and build fresh `BrowserContext`. `SIGNED_OUT`, `EXPIRED`, `UNKNOWN`, or changed bindings are rejected before ticket creation and ledger mutation. `current_context` is mandatory. This control neither refreshes an old observation nor proves its authenticity. The authorized browser path must supply actual observation and time. Context can still change between observation and action; a post-start uncertainty must be recorded as such.

Only after successful start, perform one authorized external browser send. `SENT` means local attempt start, not verified remote delivery. Do not start the same operation again. Use short observations with explicit deadlines, never an unlimited waiting loop. Tool failure or timeout is not success.

## Observation and continuation

Within a bounded window, read the matching user message, associated answer, and positive completion evidence. Hash the exact prompt with SHA-256; the request hash also covers parameters and cannot replace the prompt hash. User and answer messages have separate local identifiers. Every hash reference needs reviewable sanitized evidence.

Preserve intermediate observations until the window ends and record only one final window result. An unfinished answer requires a partial or unknown-delivery outcome. Do not later overwrite that outcome. This probe recorder does not implement full incremental acquisition or recovery.

```sh
python tools/run_browser_probe.py record --database /private/probe.sqlite3 --ticket /private/ticket.json --input /private/observation.json --expected-revision 4
python tools/run_browser_probe.py inspect --database /private/probe.sqlite3 --ticket /private/ticket.json
```

Inspection reads state and permitted continuation without sending. Interruption after start requires delivery verification. A complete raw answer is not formal confirmation. For the limited continuation probe, request a genuine JSON object with only a textual `answer`, then use `ledger.validate_response` with `P02MockAnswer.v1`. `ledger.confirm_result` is allowed only after actual positive validation. This establishes that limited schema, not council quality or full product conformance. Do not replace invalid live input with fabricated content.

After genuine limited confirmation, prepare a new continuation intent in the same binding/conversation with fresh identifiers and marker; start recording before the external action. Verify real conversation linkage and continuation with two distinct live observations. Local identifier matching alone cannot prove service continuation.

## Historical P03 acceptance

P03 criteria cover real send/receive and same-conversation continuation, expiration/uncertain observation behavior, and updated capability/estimate records. Preparation tests alone cannot meet them. P03's recorded acceptance is historical; read current progress instead of reopening P03 or blocking already accepted P04 from this example.

Do not wait indefinitely for natural expiration. A controlled sign-out can test loss of access and start refusal when recorded as `CONTROLLED_SIGN_OUT`; it does not measure session lifetime or natural expiration. Contract tests separately cover synthetic `EXPIRED` input and must disclose that origin. Review both real positive/negative evidence and these limits when evaluating the historical gate.

```sh
python tools/run_browser_probe_tests.py
python tools/qualityctl.py navigation
```

Tests need no key or account. Select the supervisor workflow when running the full development suite; avoid separately rerunning a suite it already covers. Bounds reduce unlimited waits without guaranteeing that every environment or service hang is impossible.
