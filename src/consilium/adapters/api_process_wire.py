"""Private process envelopes: context binding, not provider provenance."""

import base64
import hashlib
import json
from dataclasses import asdict
from uuid import UUID

from consilium.adapters.api_codec import MAX_BYTES, ApiObservation, WireRequest
from consilium.adapters.api_http import HttpGrant, HttpOutcome

MAX_PROCESS_BYTES = 3 * 1048576


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate")
        value[key] = item
    return value


def _constant(_value):
    raise ValueError("nonfinite")


def _json(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_PROCESS_BYTES:
        raise ValueError("size")
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > 64:
                raise ValueError("depth")
        elif byte in (93, 125):
            depth -= 1
    value = json.loads(
        raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant
    )
    json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return value


def _encoded(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def grant_data(grant):
    value = asdict(grant)
    value["account_binding_id"] = str(grant.account_binding_id)
    value["user_action_id"] = str(grant.user_action_id)
    return value


def grant_hash(grant):
    return hashlib.sha256(_encoded(grant_data(grant))).hexdigest()


def wire_hash(wire):
    """Bind decoding mode as well as exact body and provider/model."""
    return hashlib.sha256(
        _encoded(
            {
                "provider": wire.provider,
                "model": wire.model,
                "streaming": wire.streaming,
                "body_sha256": wire.sha256,
            }
        )
    ).hexdigest()


def encode_process_request(grant, wire, attempt_id, timeout_seconds):
    invalid = False
    try:
        raw = _encoded(
            {
                "schema_version": 1,
                "kind": "API_PROCESS_REQUEST_V1",
                "grant": grant_data(grant),
                "wire": {
                    "provider": wire.provider,
                    "model": wire.model,
                    "streaming": wire.streaming,
                    "body_base64": base64.b64encode(wire.body).decode("ascii"),
                },
                "attempt_id": str(attempt_id),
                "timeout_seconds": timeout_seconds,
            }
        )
        decode_process_request(raw)
    except Exception:  # noqa: BLE001 -- never expose request or credential source details
        invalid = True
    if invalid:
        raise ValueError("API_PROCESS_REQUEST_INVALID")
    return raw


def decode_process_request(raw):
    import math

    invalid = False
    try:
        value = _json(raw)
        if (
            type(value) is not dict
            or set(value)
            != {
                "schema_version",
                "kind",
                "grant",
                "wire",
                "attempt_id",
                "timeout_seconds",
            }
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or value["kind"] != "API_PROCESS_REQUEST_V1"
        ):
            raise ValueError("schema")
        g, w = value["grant"], value["wire"]
        if (
            type(g) is not dict
            or set(g) != set(HttpGrant.__dataclass_fields__)
            or type(w) is not dict
            or set(w) != {"provider", "model", "streaming", "body_base64"}
        ):
            raise ValueError("fields")
        for field in ("account_binding_id", "user_action_id"):
            if type(g[field]) is not str:
                raise ValueError("uuid")
            g[field] = UUID(g[field])
        if type(value["attempt_id"]) is not str or type(w["body_base64"]) is not str:
            raise ValueError("type")
        attempt = UUID(value["attempt_id"])
        body = base64.b64decode(w["body_base64"], validate=True)
        if (
            base64.b64encode(body).decode("ascii") != w["body_base64"]
            or not body
            or len(body) > MAX_BYTES
        ):
            raise ValueError("body")
        wire = WireRequest(w["provider"], w["model"], body, w["streaming"])
        grant = HttpGrant(**g)
        grant.validate(wire)
        timeout = value["timeout_seconds"]
        if (
            not attempt.int
            or type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 900
        ):
            raise ValueError("budget")
    except Exception:  # noqa: BLE001 -- private input validation
        invalid = True
    if invalid:
        raise ValueError("API_PROCESS_REQUEST_INVALID")
    return grant, wire, attempt, timeout


def _outcome(value, provider):
    if type(value) is not dict or set(value) != {"delivery", "code", "observation"}:
        raise ValueError("outcome")
    observation = value["observation"]
    if observation is not None:
        if type(observation) is not dict or set(observation) != set(
            ApiObservation.__dataclass_fields__
        ):
            raise ValueError("observation")
        content, state = observation["content"], observation["state"]
        if state not in {"NONE", "COMPLETE", "PARTIAL", "INVALID"} or (
            state == "NONE"
            and content is not None
            or state != "NONE"
            and (type(content) is not str or not content.strip())
        ):
            raise ValueError("content")
        if content is not None and len(content.encode("utf-8")) > MAX_BYTES:
            raise ValueError("size")
        from consilium.adapters.api_codec import _count, _identifier, _reason

        _identifier(observation["response_id"])
        reason = _reason(observation["finish_reason"])
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            _count(observation[key])
        if state == "COMPLETE" and reason != (
            "STOP" if provider == "google" else "stop"
        ):
            raise ValueError("finish")
        observation = ApiObservation(**observation)
        if value["code"] != "RESPONSE_" + state:
            raise ValueError("code")
    elif value["code"] not in {
        "TRANSPORT_INTERRUPTED",
        "INVALID_HTTP_FRAMES",
        "AUTH_REQUIRED",
        "QUOTA",
        "HTTP_ERROR",
        "MALFORMED_RESPONSE",
    }:
        raise ValueError("code")
    delivery = (
        "CONFIRMED_DELIVERY"
        if observation is not None and observation.content
        else "UNKNOWN_DELIVERY"
    )
    if value["delivery"] != delivery:
        raise ValueError("delivery")
    return HttpOutcome(delivery, value["code"], observation)


def encode_process_outcome(outcome, grant, wire, attempt_id):
    invalid = False
    try:
        if type(outcome) is not HttpOutcome:
            raise ValueError("type")
        raw = _encoded(
            {
                "schema_version": 1,
                "kind": "API_PROCESS_OUTCOME_V1",
                "grant_sha256": grant_hash(grant),
                "request_sha256": wire_hash(wire),
                "attempt_id": str(attempt_id),
                "outcome": asdict(outcome),
            }
        )
        decode_process_outcome(raw, grant, wire, attempt_id)
    except Exception:  # noqa: BLE001 -- private response validation
        invalid = True
    if invalid:
        raise ValueError("API_PROCESS_OUTCOME_INVALID")
    return raw


def decode_process_outcome(raw, grant, wire, attempt_id):
    invalid = False
    try:
        value = _json(raw)
        if (
            type(value) is not dict
            or set(value)
            != {
                "schema_version",
                "kind",
                "grant_sha256",
                "request_sha256",
                "attempt_id",
                "outcome",
            }
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or value["kind"] != "API_PROCESS_OUTCOME_V1"
            or value["grant_sha256"] != grant_hash(grant)
            or value["request_sha256"] != wire_hash(wire)
            or value["attempt_id"] != str(attempt_id)
        ):
            raise ValueError("binding")
        result = _outcome(value["outcome"], wire.provider)
    except Exception:  # noqa: BLE001 -- private response validation
        invalid = True
    if invalid:
        raise ValueError("API_PROCESS_OUTCOME_INVALID")
    return result
