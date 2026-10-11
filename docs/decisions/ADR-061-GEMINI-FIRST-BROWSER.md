# ADR-061 — Select Gemini as the first P09 browser provider

Status: user-authorized provider priority change; no live connection acceptance.

## Decision

The user requested Gemini or GLM instead of Qwen. Select Gemini (provider_id:
google), which is already one of the five protected V1 providers. Its browser
origin is https://gemini.google.com. GLM is not selected in this task; adding a
sixth provider would require a separate scope and integration decision.

This changes the first P09 provider, not the protected V1 coverage. Existing
Qwen parsers, tests, immutable evidence and historical decisions remain intact
for their actual provider. Do not rename a Qwen capture, thinking prefix or
completion rule into a Gemini contract. API implementations and the P08 work
deferral are unchanged. Permanent GitHub authorization is preserved.

## Implementation boundary

PROGRESS.json.resume.p09_preparation.first_provider records the canonical selected
provider and origin. resume.next_action and next_task explicitly target Gemini.
The generic owned CDP layout reader supports exact HTTPS origins and remains
usable after genuine Gemini selectors and independent authenticated context are
observed. This is provider selection and preparation; no new live Gemini driver,
send permission, account login or successful product council path is claimed.

The exact Gemini model_id remains null until independently observed in an
accessible authenticated browser. A product or service name cannot establish
which model, account tier, quota or capacity is in use. Current account access,
selectors, response mapping and live verification remain unknown.

## Network and validation

Add only gemini.google.com to the environment network draft, preserving existing
custom domains, presets, startup instructions, repository membership and secrets.
Draft saving does not activate runtime access. Login or resource destinations
must be added only when independently observed and required; do not broaden to
all Google domains. No API key, cookie, password or provider call is requested.

This documentation/status change uses one registered supervised native run,
scoped quality/type checks, source-bound receipts and generated handoff verification.
No synthetic Gemini behavior test or duplicate Chromium fixture run is invented
for unchanged browser code. Any availability observation is separate from model
execution and live acceptance.

## Remaining work

Activate the saved environment draft, acquire a supported secure authenticated
Gemini browser, independently observe account/model/conversation and actual
selectors, then map messages to product operations with genuine completion and
recovery evidence. P09 remains unaccepted; formal current_phase stays P08 while
execution_phase is P09 under the existing authorized sequence exception. Do not
return to P08 implementation while the user's deferral is active.
