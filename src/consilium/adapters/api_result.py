"""Bind private process outcomes to prepared product requests; no live admission."""

import json
import math

from consilium.adapters.api_http import AccessBlocked
from consilium.adapters.api_plan import verify_plan
from consilium.adapters.api_process_wire import decode_process_outcome
from consilium.core.contracts import Delivery, Failure, ResponseState, TransportResult


def bind_api_outcome(raw, plan, request, grant, profile, *, elapsed_seconds):
    """Pure conversion. Caller must separately prove live admission and provenance.

    Neither this function nor a COMPLETE transport result confirms an application
    response, changes the ledger, opens a socket or authorizes another attempt.
    """
    verify_plan(plan, request, grant, profile)
    if (
        type(elapsed_seconds) not in (int, float)
        or not math.isfinite(elapsed_seconds)
        or not 0 <= elapsed_seconds <= request.timeout_seconds + 5
    ):
        raise AccessBlocked("API_RESULT_ELAPSED_INVALID")
    outcome = decode_process_outcome(
        raw, grant, plan.wire, request.intent.identity.attempt_id
    )
    observation = outcome.observation
    failure = {
        "AUTH_REQUIRED": Failure.SESSION_EXPIRED,
        "QUOTA": Failure.QUOTA,
        "HTTP_ERROR": Failure.SEND_REJECTED,
        "MALFORMED_RESPONSE": Failure.SEND_REJECTED,
        "INVALID_HTTP_FRAMES": Failure.SEND_REJECTED,
    }.get(outcome.code, Failure.NONE)
    state = (
        ResponseState.NONE if observation is None else ResponseState(observation.state)
    )
    if state == ResponseState.INVALID:
        failure = Failure.INVALID_RESPONSE
    metadata = (
        ()
        if observation is None
        else (
            "API_METADATA:"
            + json.dumps(
                {
                    "finish_reason": observation.finish_reason,
                    "input_tokens": observation.input_tokens,
                    "output_tokens": observation.output_tokens,
                    "total_tokens": observation.total_tokens,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    )
    return TransportResult(
        identity=request.intent.identity,
        request_hash=request.intent.request_hash,
        connection_id=request.connection.connection_id,
        connection_revision=request.intent.connection_revision,
        delivery=Delivery(outcome.delivery),
        response_state=state,
        content=None if observation is None else observation.content,
        failure=failure,
        response_id=None if observation is None else observation.response_id,
        elapsed_seconds=float(elapsed_seconds),
        evidence=(
            "API_PREPARED_RESULT_NOT_LIVE_CERTIFICATION",
            outcome.code,
            "WIRE_SHA256:" + plan.wire.sha256,
            "PROFILE_SHA256:" + profile.content_hash,
            "DESTINATION_SHA256:" + plan.destination_hash,
        )
        + metadata,
    )
