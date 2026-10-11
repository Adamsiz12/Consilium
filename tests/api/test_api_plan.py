"""Declared plans cannot certify capacity, enable transport or alter frozen bytes."""

import unittest
from dataclasses import replace
from uuid import uuid4

from consilium.adapters.api_http import AccessBlocked, HttpGrant
from consilium.adapters.api_plan import ApiProfile, prepare_api, verify_plan
from consilium.core.contracts import (
    AdapterRequest,
    ConnectionSpec,
    FrozenInput,
    GenerationParameters,
    Message,
    OperationIdentity,
    OperationIntent,
)


class ApiPlanTests(unittest.TestCase):
    def setUp(self):
        account = uuid4()
        self.grant = HttpGrant(
            "google",
            "fixture",
            account,
            uuid4(),
            "https://generativelanguage.googleapis.com/v1beta/models/fixture:generateContent",
            "GEMINI_API_KEY",
        )
        self.profile = ApiProfile(
            provider="google",
            model="fixture",
            endpoint=self.grant.endpoint,
            revision=1,
            context_capacity=100,
            max_output_tokens=20,
            streaming=False,
            tokenizer_id="fixture-only",
            implementation_hash="a" * 64,
        )
        connection = ConnectionSpec(
            connection_id=uuid4(),
            provider_id="google",
            model_id="fixture",
            mode="API",
            account_binding_id=account,
        )
        frozen = FrozenInput(
            messages=(Message(role="USER", content="پرسش"),),
            parameters=GenerationParameters(max_output_tokens=20),
        )
        intent = OperationIntent(
            identity=OperationIdentity(
                logical_operation_id=uuid4(), attempt_id=uuid4()
            ),
            debate_id=uuid4(),
            round_id=uuid4(),
            participant_id=uuid4(),
            connection_id=connection.connection_id,
            expected_revision=0,
            connection_revision=0,
            frozen_input=frozen,
            request_hash=frozen.content_hash,
        )
        self.request = AdapterRequest(
            intent=intent,
            connection=connection,
            timeout_seconds=10.0,
            transport_binding_hash=self.profile.content_hash,
        )

    def plan(self, **kw):
        return prepare_api(
            self.request,
            self.grant,
            self.profile,
            input_tokens=kw.pop("input_tokens", 80),
            **kw,
        )

    def test_exact_budget_boundary_and_unicode_do_not_enable_live(self):
        p = self.plan()
        verify_plan(p, self.request, self.grant, self.profile)
        self.assertFalse(p.live_admitted)
        self.assertFalse(self.grant.enabled)
        self.assertIn("پرسش", p.wire.body.decode())
        self.assertEqual(p.input_tokens + p.reserved_output_tokens, 100)

    def test_invalid_capacity_bool_and_unsupported_stream_fail_before_send(self):
        for count in (81, 0, -1, True, 2.5):
            with self.subTest(count=count), self.assertRaises(AccessBlocked):
                self.plan(input_tokens=count)
        with self.assertRaises(AccessBlocked):
            self.plan(streaming=True)

    def test_account_destination_and_profile_revision_are_bound(self):
        for grant in (
            replace(self.grant, account_binding_id=uuid4()),
            replace(self.grant, model="other"),
        ):
            with self.assertRaises(AccessBlocked):
                prepare_api(self.request, grant, self.profile, input_tokens=1)
        with self.assertRaises(AccessBlocked):
            prepare_api(
                self.request,
                self.grant,
                self.profile.model_copy(update={"revision": 2}),
                input_tokens=1,
            )

    def test_forged_wire_and_live_admission_are_rejected(self):
        p = self.plan()
        for changed in (
            replace(p, wire=replace(p.wire, body=b"{}")),
            replace(p, live_admitted=True),
            replace(p, request_hash="b" * 64),
            replace(p, reserved_output_tokens=1),
        ):
            with self.assertRaises(AccessBlocked):
                verify_plan(changed, self.request, self.grant, self.profile)

    def test_unvalidated_request_with_wrong_frozen_hash_has_private_error(self):
        intent = type(self.request.intent).model_construct(
            **{
                **self.request.intent.model_dump(mode="python"),
                "request_hash": "b" * 64,
            }
        )
        request = type(self.request).model_construct(
            **{**self.request.model_dump(mode="python"), "intent": intent}
        )
        with self.assertRaisesRegex(AccessBlocked, "^API_PLAN_INPUT_INVALID$") as error:
            prepare_api(request, self.grant, self.profile, input_tokens=1)
        self.assertIsNone(error.exception.__context__)

    def test_unvalidated_profile_invalid_capacity_has_private_error(self):
        for changes in (
            {"context_capacity": True},
            {"max_output_tokens": -1},
            {"revision": -1},
        ):
            profile = type(self.profile).model_construct(
                **{**self.profile.model_dump(mode="python"), **changes}
            )
            with self.assertRaisesRegex(AccessBlocked, "^API_PLAN_INPUT_INVALID$"):
                prepare_api(self.request, self.grant, profile, input_tokens=1)

    def test_unvalidated_request_invalid_timeout_has_private_error(self):
        for timeout in (True, 0, float("nan")):
            request = type(self.request).model_construct(
                **{**self.request.model_dump(mode="python"), "timeout_seconds": timeout}
            )
            with self.assertRaisesRegex(AccessBlocked, "^API_PLAN_INPUT_INVALID$"):
                prepare_api(request, self.grant, self.profile, input_tokens=1)
