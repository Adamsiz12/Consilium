# Read-only CDP acquisition

This is preparation, not accepted Qwen/live product integration. It neither opens a browser nor navigates/logs in. Endpoint, target, and selector must come from explicitly authorized observation, not model inference.

Optional transport dependencies:

```sh
python -m pip install '.[browser-read]'
```

Example with values supplied by authorized acquisition configuration:

```python
from consilium.adapters.cdp_process_reader import CdpProcessDomReader

reader = CdpProcessDomReader(
    endpoint=endpoint, target_id=target_id, expected_url=expected_url,
    selector=observed_selector, timeout_seconds=10,
)
observation = reader()
```

The owned reader process has a bounded deadline plus up to five seconds for cleanup; it reads only an existing target. Keep acquired data in a private journal with output-size limits before handoff. QwenProcessReader accepts only versioned Qwen packets, not arbitrary raw HTML. No heuristic converts HTML into a verified complete answer.

HTML is private untrusted data. Do not place it in public logs, receipts, Git, or transfer archives. Loopback and content hashes cannot prove browser/account identity. DOM reading is not atomic: document/frame navigation changes are rejected, while same-document edits still require answer-observation checks.

Optional transport fixture:

```sh
python tools/run_cdp_transport_probe.py
```

Its receipt is REAL_LOOPBACK_WEBSOCKET_CDP_FIXTURE_NOT_LIVE_BROWSER: a real local transport fixture, not live browser evidence. Real integration still needs observed selectors, independent account/model/conversation context, and negative context-change checks. A fixture does not close a phase. The connected browser is not an owned worker and is not killed for reader cleanup.
