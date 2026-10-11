"""Process envelopes bind exact grants, requests and attempts without secrets."""

import json
import unittest
from dataclasses import replace
from uuid import UUID, uuid4

from consilium.adapters.api_codec import ApiObservation, encode
from consilium.adapters.api_http import HttpGrant, HttpOutcome
from consilium.adapters.api_process_wire import (
    decode_process_outcome,
    decode_process_request,
    encode_process_outcome,
    encode_process_request,
)
from consilium.core.contracts import FrozenInput, Message


class ProcessWireTests(unittest.TestCase):
    def setUp(self):
        self.grant = HttpGrant(
            "google",
            "fixture",
            uuid4(),
            uuid4(),
            "https://generativelanguage.googleapis.com/v1beta/models/fixture:generateContent",
            "GEMINI_API_KEY",
            True,
            True,
        )
        self.wire = encode(
            "google",
            "fixture",
            FrozenInput(messages=(Message(role="USER", content="متن خصوصی"),)),
        )
        self.attempt = uuid4()
        self.request = encode_process_request(self.grant, self.wire, self.attempt, 30)
        self.outcome = HttpOutcome(
            "CONFIRMED_DELIVERY",
            "RESPONSE_COMPLETE",
            ApiObservation("پاسخ", "COMPLETE", "STOP", "remote-1"),
        )
        self.response = encode_process_outcome(
            self.outcome, self.grant, self.wire, self.attempt
        )

    def decode_response(self, raw):
        return decode_process_outcome(raw, self.grant, self.wire, self.attempt)

    def test_exact_round_trip(self):
        self.assertEqual(
            decode_process_request(self.request),
            (self.grant, self.wire, self.attempt, 30),
        )
        self.assertEqual(self.decode_response(self.response), self.outcome)

    def test_request_top_level_unknown_missing_or_wrong_version(self):
        value = json.loads(self.request)
        for field, item in (
            ("schema_version", True),
            ("schema_version", 2),
            ("kind", "other"),
            ("extra", "private"),
        ):
            bad = dict(value, **{field: item})
            with self.assertRaisesRegex(ValueError, "^API_PROCESS_REQUEST_INVALID$"):
                decode_process_request(json.dumps(bad).encode())
        del value["timeout_seconds"]
        with self.assertRaises(ValueError):
            decode_process_request(json.dumps(value).encode())

    def test_request_empty_noncanonical_or_invalid_base64(self):
        for body in ("", "Zh==", "%%%", 1, None):
            value = json.loads(self.request)
            value["wire"]["body_base64"] = body
            with self.assertRaises(ValueError):
                decode_process_request(json.dumps(value).encode())

    def test_request_denied_grant_or_wire_binding(self):
        for field, item in (
            ("enabled", False),
            ("free_only_confirmed", False),
            ("enabled", 1),
            ("endpoint", "https://evil.invalid/send"),
            ("credential_env", "HOME"),
            ("model", "other"),
            ("account_binding_id", str(UUID(int=0))),
        ):
            value = json.loads(self.request)
            value["grant"][field] = item
            with self.assertRaises(ValueError):
                decode_process_request(json.dumps(value).encode())

    def test_request_uuid_and_budget_rejected(self):
        for field, item in (
            ("attempt_id", str(UUID(int=0))),
            ("attempt_id", "wrong"),
            ("attempt_id", 12),
            ("timeout_seconds", True),
            ("timeout_seconds", 0),
            ("timeout_seconds", 901),
        ):
            value = json.loads(self.request)
            value[field] = item
            with self.assertRaises(ValueError):
                decode_process_request(json.dumps(value).encode())

    def test_duplicate_keys_nonfinite_surrogates_depth_and_size_rejected(self):
        for raw in (
            b'{"schema_version":1,"schema_version":1}',
            b'{"x":NaN}',
            b'{"x":1e999}',
            b'{"x":"\\ud800"}',
            b"[" * 65 + b"]" * 65,
            b"x" * (3 * 1048576 + 1),
            b"\xff",
        ):
            with self.assertRaises(ValueError):
                decode_process_request(raw)
            with self.assertRaises(ValueError):
                self.decode_response(raw)

    def test_response_context_change_is_rejected(self):
        for field, item in (
            ("grant_sha256", "0" * 64),
            ("request_sha256", "0" * 64),
            ("attempt_id", str(uuid4())),
            ("schema_version", True),
            ("kind", "other"),
        ):
            value = json.loads(self.response)
            value[field] = item
            with self.assertRaisesRegex(ValueError, "^API_PROCESS_OUTCOME_INVALID$"):
                self.decode_response(json.dumps(value).encode())

    def test_response_observation_types_and_completion_proof(self):
        for field, item in (
            ("content", " "),
            ("content", 4),
            ("state", "UNKNOWN"),
            ("finish_reason", "MAX_TOKENS"),
            ("input_tokens", True),
            ("total_tokens", -1),
            ("response_id", {}),
        ):
            value = json.loads(self.response)
            value["outcome"]["observation"][field] = item
            with self.assertRaises(ValueError):
                self.decode_response(json.dumps(value).encode())

    def test_response_delivery_and_code_cannot_upgrade_observation(self):
        for field, item in (
            ("delivery", "UNKNOWN_DELIVERY"),
            ("code", "RESPONSE_PARTIAL"),
        ):
            value = json.loads(self.response)
            value["outcome"][field] = item
            with self.assertRaises(ValueError):
                self.decode_response(json.dumps(value).encode())

    def test_partial_and_invalid_content_are_delivery_not_acceptance(self):
        for state in ("PARTIAL", "INVALID"):
            outcome = replace(
                self.outcome,
                code="RESPONSE_" + state,
                observation=replace(self.outcome.observation, state=state),
            )
            raw = encode_process_outcome(outcome, self.grant, self.wire, self.attempt)
            self.assertEqual(self.decode_response(raw), outcome)

    def test_none_and_transport_errors_never_confirm_delivery(self):
        cases = [
            HttpOutcome("UNKNOWN_DELIVERY", code)
            for code in (
                "TRANSPORT_INTERRUPTED",
                "AUTH_REQUIRED",
                "QUOTA",
                "HTTP_ERROR",
                "MALFORMED_RESPONSE",
            )
        ]
        cases.append(
            HttpOutcome(
                "UNKNOWN_DELIVERY",
                "RESPONSE_NONE",
                ApiObservation(None, "NONE", None, None),
            )
        )
        for outcome in cases:
            self.assertEqual(
                self.decode_response(
                    encode_process_outcome(outcome, self.grant, self.wire, self.attempt)
                ),
                outcome,
            )

    def test_decoding_mode_is_bound_even_when_body_is_unchanged(self):
        with self.assertRaises(ValueError):
            decode_process_outcome(
                self.response,
                self.grant,
                replace(self.wire, streaming=True),
                self.attempt,
            )
