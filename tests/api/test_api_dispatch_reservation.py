"""Reservation rejection is atomic and cannot consume historical previews."""

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import test_api_dispatch_preflight

from consilium.adapters.api_http import AccessBlocked
from consilium.shell.api_dispatch_preflight import inspect_api_dispatch
from consilium.shell.api_dispatch_reservation import reserve_api_dispatch
from consilium.shell.storage import SQLiteStore


class ApiDispatchReservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_api_dispatch_preflight.ApiDispatchPreflightTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def reserve(self, code, **changes):
        f = self.fixture
        args = {"store": f.store, "plan": f.plan, "request": f.request,
                "grant": f.grant, "profile": f.profile, "expected_revision": f.revision}
        args.update(changes)
        before = tuple(f.store._db.iterdump())
        with (
            patch("consilium.adapters.api_http.credential_value",
                  side_effect=AssertionError("credential read")),
            patch("consilium.adapters.api_http.http.client.HTTPSConnection",
                  side_effect=AssertionError("network contact")),
            self.assertRaises(AccessBlocked) as raised,
        ):
            reserve_api_dispatch(**args)
        self.assertEqual(str(raised.exception), code)
        self.assertIsNone(raised.exception.__context__)
        self.assertEqual(tuple(f.store._db.iterdump()), before)
        self.assertFalse(f.store._db.in_transaction)

    def test_missing_admission_rolls_back_and_remains_prepared_after_reopen(self):
        self.reserve("API_RESERVATION_CONTEXT_ADMISSION_REQUIRED")
        self.fixture.store.close()
        self.fixture.store = SQLiteStore(self.fixture.database)
        self.reserve("API_RESERVATION_CONTEXT_ADMISSION_REQUIRED")

    def test_repeated_rejection_never_creates_a_reservation(self):
        for _ in range(2):
            self.reserve("API_RESERVATION_CONTEXT_ADMISSION_REQUIRED")

    def test_validation_occurs_inside_immediate_write_transaction(self):
        f = self.fixture
        statements = []
        f.store._db.set_trace_callback(statements.append)
        try:
            with patch("consilium.shell.api_dispatch_reservation.verify_plan") as verify:
                verify.side_effect = lambda *args: self.assertTrue(f.store._db.in_transaction)
                self.reserve("API_RESERVATION_CONTEXT_ADMISSION_REQUIRED")
        finally:
            f.store._db.set_trace_callback(None)
        self.assertIn("BEGIN IMMEDIATE", statements)
        self.assertIn("ROLLBACK", statements)
        self.assertNotIn("COMMIT", statements[statements.index("BEGIN IMMEDIATE"):])

    def test_forged_live_plan_or_changed_wire_is_rejected(self):
        f = self.fixture
        for plan in (replace(f.plan, live_admitted=True),
                     replace(f.plan, wire=replace(f.plan.wire, body=b"private"))):
            self.reserve("API_RESERVATION_INPUT_INVALID", plan=plan)

    def test_invalid_revision_is_rejected(self):
        for revision in (True, -1, 4.0):
            self.reserve("API_RESERVATION_REVISION_INVALID", expected_revision=revision)

    def test_stale_revision_is_rejected(self):
        self.reserve("API_RESERVATION_LEDGER_CONFLICT", expected_revision=3)

    def test_preview_does_not_authorize_after_concurrent_binding_change(self):
        f = self.fixture
        preview = inspect_api_dispatch(f.store, f.plan, f.request, f.grant,
                                       f.profile, expected_revision=f.revision)
        with SQLiteStore(f.database) as other:
            other.bind_connection(f.request.intent.debate_id, f.request.intent.participant_id,
                                  f.request.connection, expected_revision=f.revision,
                                  expected_connection_revision=0, actor="test user", reason="test replacement")
        self.reserve("API_RESERVATION_LEDGER_CONFLICT",
                     expected_revision=preview.ledger_revision)
        self.reserve("API_RESERVATION_LEDGER_CONFLICT")

    def test_claimed_live_observation_cannot_enable_reservation(self):
        f = self.fixture
        fake = SimpleNamespace(observation=SimpleNamespace(scope="LIVE_VERIFIED"))
        with (patch.object(f.store.admissions, "get", return_value=fake),
              patch.object(f.store.admissions, "require_current", return_value=fake)):
            self.reserve("API_RESERVATION_LIVE_OBSERVER_NOT_REGISTERED")

    def test_caller_transaction_is_preserved_and_not_committed(self):
        f = self.fixture
        f.store._db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(AccessBlocked, "REQUIRES_OWN_WRITE_TRANSACTION"):
                reserve_api_dispatch(f.store, f.plan, f.request, f.grant,
                                     f.profile, expected_revision=f.revision)
            self.assertTrue(f.store._db.in_transaction)
        finally:
            f.store._db.execute("ROLLBACK")
