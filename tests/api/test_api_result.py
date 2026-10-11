"""Product result binding remains pure and cannot accept or dispatch a response."""

import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

import test_api_plan

from consilium.adapters.api_codec import ApiObservation
from consilium.adapters.api_http import AccessBlocked, HttpOutcome
from consilium.adapters.api_process_wire import encode_process_outcome
from consilium.adapters.api_result import bind_api_outcome
from consilium.core.contracts import Delivery, Failure, ResponseState


class ApiResultTests(unittest.TestCase):
    def setUp(self):
        fixture = test_api_plan.ApiPlanTests()
        fixture.setUp()
        self.request, self.grant, self.profile = (
            fixture.request,
            fixture.grant,
            fixture.profile,
        )
        self.plan = fixture.plan()
        self.outcome = HttpOutcome(
            "CONFIRMED_DELIVERY",
            "RESPONSE_COMPLETE",
            ApiObservation("پاسخ", "COMPLETE", "STOP", "remote-1", 10, 5, 15),
        )

    def bind(self, outcome=None, **changes):
        outcome = self.outcome if outcome is None else outcome
        raw = encode_process_outcome(
            outcome, self.grant, self.plan.wire, self.request.intent.identity.attempt_id
        )
        args = {
            "raw": raw,
            "plan": self.plan,
            "request": self.request,
            "grant": self.grant,
            "profile": self.profile,
            "elapsed_seconds": 1,
        }
        args.update(changes)
        return bind_api_outcome(**args)

    def test_complete_preserves_exact_product_identity_and_metadata(self):
        result = self.bind()
        self.assertEqual(result.identity, self.request.intent.identity)
        self.assertEqual(result.request_hash, self.request.intent.request_hash)
        self.assertEqual(result.connection_id, self.request.connection.connection_id)
        self.assertEqual(
            result.connection_revision, self.request.intent.connection_revision
        )
        self.assertEqual(
            (result.delivery, result.response_state, result.failure, result.content),
            (Delivery.CONFIRMED, ResponseState.COMPLETE, Failure.NONE, "پاسخ"),
        )
        self.assertEqual(result.response_id, "remote-1")
        self.assertIn("API_PREPARED_RESULT_NOT_LIVE_CERTIFICATION", result.evidence)
        self.assertTrue(any('"total_tokens":15' in item for item in result.evidence))

    def test_conversion_reads_no_key_and_opens_no_connection(self):
        with (
            patch(
                "consilium.adapters.api_http.credential_value",
                side_effect=AssertionError("key read"),
            ),
            patch(
                "consilium.adapters.api_http.http.client.HTTPSConnection",
                side_effect=AssertionError("network"),
            ),
        ):
            self.assertEqual(self.bind().response_state, ResponseState.COMPLETE)
        self.assertFalse(self.grant.enabled)
        self.assertFalse(self.plan.live_admitted)

    def test_partial_and_invalid_are_preserved_without_upgrade(self):
        for state in ("PARTIAL", "INVALID"):
            outcome = replace(
                self.outcome,
                code="RESPONSE_" + state,
                observation=replace(self.outcome.observation, state=state),
            )
            result = self.bind(outcome)
            self.assertEqual(result.response_state.value, state)
            self.assertEqual(result.content, "پاسخ")
            self.assertEqual(
                result.failure,
                Failure.INVALID_RESPONSE if state == "INVALID" else Failure.NONE,
            )

    def test_error_responses_never_prove_no_send(self):
        for code, failure in (
            ("AUTH_REQUIRED", Failure.SESSION_EXPIRED),
            ("QUOTA", Failure.QUOTA),
            ("HTTP_ERROR", Failure.SEND_REJECTED),
            ("MALFORMED_RESPONSE", Failure.SEND_REJECTED),
            ("INVALID_HTTP_FRAMES", Failure.SEND_REJECTED),
            ("TRANSPORT_INTERRUPTED", Failure.NONE),
        ):
            result = self.bind(HttpOutcome("UNKNOWN_DELIVERY", code))
            self.assertEqual(
                (result.delivery, result.response_state, result.failure),
                (Delivery.UNKNOWN, ResponseState.NONE, failure),
            )
            self.assertIsNone(result.content)

    def test_empty_observation_does_not_invent_failure_cause(self):
        result = self.bind(
            HttpOutcome(
                "UNKNOWN_DELIVERY",
                "RESPONSE_NONE",
                ApiObservation(None, "NONE", None, None),
            )
        )
        self.assertEqual(
            (result.delivery, result.response_state, result.failure),
            (Delivery.UNKNOWN, ResponseState.NONE, Failure.NONE),
        )

    def test_copied_plan_cannot_claim_live_admission(self):
        with self.assertRaises(AccessBlocked):
            self.bind(plan=replace(self.plan, live_admitted=True))

    def test_account_model_destination_or_profile_change_rejected(self):
        for grant in (
            replace(self.grant, account_binding_id=uuid4()),
            replace(self.grant, model="other"),
            replace(self.grant, endpoint="https://evil.invalid/send"),
        ):
            with self.assertRaises(AccessBlocked):
                self.bind(grant=grant)
        profile = self.profile.model_copy(
            update={"revision": self.profile.revision + 1}
        )
        with self.assertRaises(AccessBlocked):
            self.bind(profile=profile)

    def test_different_attempt_cannot_reuse_same_result(self):
        identity = self.request.intent.identity.model_copy(
            update={"attempt_id": uuid4()}
        )
        intent = self.request.intent.model_copy(update={"identity": identity})
        request = self.request.model_copy(update={"intent": intent})
        with self.assertRaises(ValueError):
            self.bind(request=request)

    def test_elapsed_type_range_and_finiteness_are_explicit(self):
        for elapsed in (
            True,
            -1,
            float("nan"),
            float("inf"),
            self.request.timeout_seconds + 5.01,
        ):
            with self.assertRaisesRegex(AccessBlocked, "API_RESULT_ELAPSED_INVALID"):
                self.bind(elapsed_seconds=elapsed)
        self.assertEqual(
            self.bind(elapsed_seconds=self.request.timeout_seconds + 5).elapsed_seconds,
            self.request.timeout_seconds + 5,
        )

    def test_same_attempt_cannot_be_rebound_to_other_product_revision(self):
        for changes in (
            {"connection_revision": 1},
            {"expected_revision": 1},
            {"round_id": uuid4()},
            {"participant_id": uuid4()},
            {"debate_id": uuid4()},
        ):
            request = self.request.model_copy(
                update={"intent": self.request.intent.model_copy(update=changes)}
            )
            with self.assertRaises(AccessBlocked):
                self.bind(request=request)
        with self.assertRaises(AccessBlocked):
            self.bind(request=self.request.model_copy(update={"timeout_seconds": 11.0}))

    def test_grant_action_and_access_flags_are_bound(self):
        for grant in (
            replace(self.grant, user_action_id=uuid4()),
            replace(self.grant, enabled=True),
            replace(self.grant, free_only_confirmed=True),
        ):
            with self.assertRaises(AccessBlocked):
                self.bind(grant=grant)
