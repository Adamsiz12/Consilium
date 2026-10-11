# ADR-060 — Defer P08 work and continue P09 rendered-layout preparation

Status: user-authorized sequence exception; no phase acceptance.

## User instruction and canonical state

The user instructed that no further P08 implementation be performed, that its
unfinished tests receive a distinct label, and that remaining P09 work continue.
P00 through P07 are accepted. P08 is not complete except for an API key: successful
durable reservation, full council integration, provider coverage and executable
acceptance checks also remain incomplete. These facts cannot be reclassified as
only an unavailable credential.

Record P08_DEFERRED_INCOMPLETE_NOT_ACCEPTED as the continuation label, preserve
BLOCKED and protected ROADMAP acceptance dependencies, and set execution_phase to
P09. The formal current_phase/resume.phase remain P08 because qualityctl derives
the first unaccepted stage. No governance rule or validator is weakened. ADR-038
already permits P09 preparation; this instruction redirects the next action away
from further API implementation. Permanent GitHub authorization remains unchanged.

## Bounded P09 task

Raw HTML did not show which text participates in Chromium layout. The new reader
uses only DOM.describeNode and DOMSnapshot.captureSnapshot with a fixed computed
style list, bracketed by exact page URL/target/frame/loader checks. No Runtime
execution, navigation, clicks, provider send, credential read or live admission
is introduced. The selected backend node identifies the subtree; foreign frame
and subtree text are excluded. Malformed, oversized, hidden and fully transparent
layout is rejected or filtered conservatively. CDP's documented absent-text
sentinel and style-free document root are handled explicitly.

This contract is LAYOUT_TEXT_NOT_VIEWPORT_OR_LIVE_RESPONSE_CERTIFICATION. It is
not screenshot visibility, pixel occlusion detection, a complete history claim,
account/model authentication, rendered provider answer mapping, or completion
proof. Offscreen and occluded text may remain; conservative ancestor filtering
may omit visible overflow or descendants overriding visibility. These limits
must be retained when provider selectors are added.

The owned process uses a distinct private wire format with selector/text hashes;
it cannot be decoded as a Qwen completion packet. Existing raw-DOM behavior and
API modules are unchanged. Providers still require the existing exact HTTPS URL
policy. Only the layout contract additionally permits explicit numeric loopback
HTTP URLs with a port for local fixtures; no TLS verification is disabled.

## Validation and environment

Twelve offline tests cover scope/binding, filtering, malformed graphs and arrays,
bounds, size, mutation, command allowlists, actual Chromium sentinels, private
wire errors and owned command selection. Six additional tests run real Chromium
against a local HTTP fixture, including an actual owned child-process read.

The browser fixture owns a fresh disposable profile, local server and browser
process group; it never attaches to an existing authenticated browser. Chromium
uses no-sandbox only for this isolated local fixture because the container lacks
a usable Chromium OS sandbox. Host resolver restrictions and disabled background
services keep the test loopback-oriented; no provider is contacted. This is not
configuration for a live browser. Existing TLS/package verification is preserved.
The already-declared optional websockets==16.0 dependency was installed without
changing pins or dependency files. The explicit optional command is:

`python tools/run_cdp_layout_browser_probe.py`

It fails distinctly when Chromium is unavailable; ordinary native regression
uses portable fixtures and does not disguise missing browser capability as a
skip or acceptance. Failed local browser receipts are retained before the final
source-bound pass; full native/quality/build/transfer checks follow once.

## Remaining P09 work

Obtain actual first-provider selectors and independently observed account/model/
conversation context, map layout to correlated messages without fake completion,
then integrate genuine read/send/result provenance and full council recovery.
Real login-expiration, continuation, partial answer, ambiguous delivery and
end-to-end evidence remain incomplete. P09 is not accepted by local layout tests.
Do not return to P08 work while the user's deferral remains active.
