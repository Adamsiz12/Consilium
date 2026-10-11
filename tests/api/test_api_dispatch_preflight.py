"""Real SQLite preflight snapshots never authorize live dispatch."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import test_api_plan

from consilium.adapters.api_http import AccessBlocked
from consilium.adapters.api_plan import prepare_api
from consilium.core.contracts import DebateSpec, OperationIdentity, RoundSpec
from consilium.shell.api_dispatch_preflight import inspect_api_dispatch
from consilium.shell.storage import SQLiteStore


class ApiDispatchPreflightTests(unittest.TestCase):
    def setUp(self):
        fixture = test_api_plan.ApiPlanTests()
        fixture.setUp()
        self.grant, self.profile = fixture.grant, fixture.profile
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "state.sqlite3"
        self.store = SQLiteStore(self.database)
        self.other_participant = uuid4()
        intent = fixture.request.intent
        participants = (intent.participant_id, self.other_participant)
        self.store.create_debate(DebateSpec(
            debate_id=intent.debate_id, original_request="private fixture question",
            participant_ids=participants,
        ))
        self.store.bind_connection(
            intent.debate_id, intent.participant_id, fixture.request.connection,
            expected_revision=0, expected_connection_revision=None,
        )
        self.other_connection = fixture.request.connection.model_copy(
            update={"connection_id": uuid4()}
        )
        self.store.bind_connection(
            intent.debate_id, self.other_participant, self.other_connection,
            expected_revision=1, expected_connection_revision=None,
        )
        self.store.register_round(RoundSpec(
            round_id=intent.round_id, debate_id=intent.debate_id, number=1,
            kind="INDEPENDENT", participant_ids=participants,
        ), expected_revision=2)
        intent = intent.model_copy(update={"expected_revision": 3})
        self.store.prepare_intent(intent)
        self.request = fixture.request.model_copy(update={"intent": intent})
        self.plan = prepare_api(self.request, self.grant, self.profile, input_tokens=80)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    @property
    def revision(self):
        return self.store.checkpoint(self.request.intent.debate_id).revision

    def inspect(self, **changes):
        args = {"store": self.store, "plan": self.plan, "request": self.request,
                "grant": self.grant, "profile": self.profile,
                "expected_revision": self.revision}
        args.update(changes)
        before = tuple(self.store._db.iterdump())
        total = self.store._db.total_changes
        try:
            with (
                patch("consilium.adapters.api_http.credential_value",
                      side_effect=AssertionError("credential read")),
                patch("consilium.adapters.api_http.http.client.HTTPSConnection",
                      side_effect=AssertionError("network contact")),
            ):
                return inspect_api_dispatch(**args)
        finally:
            self.assertEqual(tuple(self.store._db.iterdump()), before)
            self.assertEqual(self.store._db.total_changes, total)
            self.assertFalse(self.store._db.in_transaction)

    def test_exact_committed_plan_is_correlated_but_missing_admission_blocks_send(self):
        report = self.inspect()
        self.assertEqual(report.attempt_id, self.request.intent.identity.attempt_id)
        self.assertEqual(report.ledger_revision, self.revision)
        self.assertEqual(report.operation_hash, self.plan.operation_hash)
        self.assertEqual(report.gate, "CONTEXT_ADMISSION_REQUIRED")
        self.assertFalse(report.dispatch_allowed)
        self.assertFalse(self.grant.enabled)
        self.assertFalse(self.plan.live_admitted)

    def test_reopened_storage_reproduces_the_same_non_authorizing_preview(self):
        before = self.inspect()
        self.store.close()
        self.store = SQLiteStore(self.database)
        self.assertEqual(self.inspect(), before)

    def test_mutated_wire_or_claimed_live_plan_is_rejected_with_private_error(self):
        for plan in (replace(self.plan, live_admitted=True),
                     replace(self.plan, wire=replace(self.plan.wire, body=b"private marker")),
                     replace(self.plan, wire=None)):
            with self.subTest(plan=type(plan).__name__), self.assertRaises(AccessBlocked) as caught:
                self.inspect(plan=plan)
            self.assertEqual(str(caught.exception), "API_PREFLIGHT_INPUT_INVALID")
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("private marker", str(caught.exception))

    def test_reencoded_changed_input_cannot_replace_persisted_intent(self):
        frozen = self.request.intent.frozen_input.model_copy(update={
            "messages": (self.request.intent.frozen_input.messages[0].model_copy(
                update={"content": "different exact input"}),),
        })
        intent = self.request.intent.model_copy(update={
            "frozen_input": frozen, "request_hash": frozen.content_hash,
        })
        request = self.request.model_copy(update={"intent": intent})
        plan = prepare_api(request, self.grant, self.profile, input_tokens=80)
        with self.assertRaisesRegex(AccessBlocked, "^API_PREFLIGHT_LEDGER_CONFLICT$"):
            self.inspect(request=request, plan=plan)

    def test_stale_and_invalid_revision_are_rejected(self):
        for revision in (True, -1, 4.0, self.revision - 1):
            with self.subTest(revision=revision), self.assertRaises(AccessBlocked):
                self.inspect(expected_revision=revision)

    def test_changed_binding_invalidates_old_plan_even_at_current_revision(self):
        self.store.bind_connection(
            self.request.intent.debate_id, self.request.intent.participant_id,
            self.request.connection.model_copy(update={"model_id": "changed-model"}),
            expected_revision=self.revision, expected_connection_revision=0,
            actor="LOCAL_USER", reason="explicit test binding change",
        )
        with self.assertRaisesRegex(AccessBlocked, "^API_PREFLIGHT_LEDGER_CONFLICT$"):
            self.inspect()

    def test_started_or_interrupted_attempt_is_not_prepared_again(self):
        self.store.ledger.begin_send(self.request, expected_revision=self.revision)
        with self.assertRaises(AccessBlocked):
            self.inspect()
        self.store.ledger.mark_interrupted(
            self.request.intent.identity.attempt_id, expected_revision=self.revision
        )
        with self.assertRaises(AccessBlocked):
            self.inspect()

    def test_another_outstanding_operation_blocks_the_prepared_candidate(self):
        self.store.ledger.begin_send(self.request, expected_revision=self.revision)
        intent = self.request.intent.model_copy(update={
            "identity": OperationIdentity(logical_operation_id=uuid4(), attempt_id=uuid4()),
            "participant_id": self.other_participant,
            "connection_id": self.other_connection.connection_id,
            "expected_revision": self.revision,
        })
        self.store.prepare_intent(intent)
        request = self.request.model_copy(update={
            "intent": intent, "connection": self.other_connection,
        })
        plan = prepare_api(request, self.grant, self.profile, input_tokens=80)
        with self.assertRaises(AccessBlocked):
            self.inspect(request=request, plan=plan)

    def test_explicit_wait_gate_blocks_without_mutation(self):
        # A focused gate fixture: change only wait state before taking the snapshot.
        self.store._db.execute("UPDATE debates SET wait_state='WAITING_DECISION'")
        with self.assertRaises(AccessBlocked):
            self.inspect()

    def test_old_round_is_rejected_even_with_matching_input_and_revision(self):
        newer = RoundSpec(
            round_id=uuid4(), debate_id=self.request.intent.debate_id, number=2,
            kind="REVIEW", participant_ids=(self.request.intent.participant_id,
                                            self.other_participant),
        )
        # Adversarial storage fixture, not an authorized round-creation action.
        self.store._db.execute("INSERT INTO rounds VALUES(?,?,?,?)", (
            str(newer.round_id), str(newer.debate_id), newer.number,
            self.store._public(newer.model_dump(mode="json")),
        ))
        with self.assertRaises(AccessBlocked):
            self.inspect()

    def test_concurrent_binding_change_does_not_mix_read_snapshot_or_grant_permission(self):
        expected = self.revision
        original_get = self.store.ledger.get_attempt
        with SQLiteStore(self.database) as other:
            def change_after_first_read(attempt):
                record = original_get(attempt)
                other.bind_connection(
                    self.request.intent.debate_id, self.request.intent.participant_id,
                    self.request.connection.model_copy(update={"model_id": "new-model"}),
                    expected_revision=expected, expected_connection_revision=0,
                    actor="LOCAL_USER", reason="concurrent test change",
                )
                return record

            with patch.object(self.store.ledger, "get_attempt", side_effect=change_after_first_read):
                report = inspect_api_dispatch(
                    self.store, self.plan, self.request, self.grant, self.profile,
                    expected_revision=expected,
                )
        self.assertEqual(report.ledger_revision, expected)
        self.assertFalse(report.dispatch_allowed)
        self.assertEqual(self.revision, expected + 1)
        with self.assertRaises(AccessBlocked):
            self.inspect(expected_revision=expected)

    def test_local_claim_of_a_live_observer_cannot_open_dispatch(self):
        # Synthetic trust-boundary case, not a genuine persisted admission proof.
        claimed = SimpleNamespace(observation=SimpleNamespace(scope="LIVE_VERIFIED"))
        with (patch.object(self.store.admissions, "get", return_value=claimed),
              patch.object(self.store.admissions, "require_current", return_value=claimed)):
            report = self.inspect()
        self.assertEqual(report.gate, "LIVE_OBSERVER_NOT_REGISTERED")
        self.assertFalse(report.dispatch_allowed)
        with self.assertRaises(ValueError):
            replace(report, dispatch_allowed=True)

    def test_missing_attempt_is_rejected_without_creating_one(self):
        intent = self.request.intent.model_copy(update={
            "identity": OperationIdentity(logical_operation_id=uuid4(), attempt_id=uuid4()),
        })
        request = self.request.model_copy(update={"intent": intent})
        plan = prepare_api(request, self.grant, self.profile, input_tokens=80)
        with self.assertRaises(AccessBlocked):
            self.inspect(request=request, plan=plan)

    def test_uncommitted_caller_transaction_cannot_be_used_as_a_snapshot(self):
        with self.store._transaction():
            before = self.store._db.total_changes
            with self.assertRaisesRegex(AccessBlocked, "OWN_READ_SNAPSHOT"):
                inspect_api_dispatch(self.store, self.plan, self.request,
                                     self.grant, self.profile, expected_revision=self.revision)
            self.assertTrue(self.store._db.in_transaction)
            self.assertEqual(self.store._db.total_changes, before)
