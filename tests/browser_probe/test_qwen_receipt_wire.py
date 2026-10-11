"""Versioned receipt transfer through an actual bounded subprocess, offline."""

import json
import sys
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import test_qwen_capture_journal
import test_qwen_site_reader

from consilium.adapters.qwen_process_reader import (
    QwenProcessReader,
    decode_reader_output,
    encode_reader_output,
)
from consilium.adapters.qwen_site_reader import QwenSiteReader
from consilium.shell.qwen_capture_ingest import record_qwen_read

FIXTURE = Path(__file__).with_name("qwen_reader_fixture.py")


class QwenReceiptWireTests(unittest.TestCase):
    def setUp(self):
        self.f = test_qwen_capture_journal.QwenCaptureJournalTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        surface = test_qwen_site_reader.QwenSurface(
            test_qwen_site_reader.URL, "tab-1", "document-1", self.f.f.f.context
        )
        source = test_qwen_site_reader.Source(surface, self.f.raw)
        self.observation = QwenSiteReader(
            source, expected_url=surface.url, expected_tab_id=surface.tab_id
        ).read_with_receipt()
        self.raw = encode_reader_output(self.observation)
        self.value = json.loads(self.raw)
        self.path = self.f.root / "wire.json"
        self.path.write_bytes(self.raw)

    def process(self, mode="success", timeout=10):
        return QwenProcessReader((sys.executable, str(FIXTURE), mode, str(self.path)),
                                 timeout_seconds=timeout)

    def test_version_two_round_trip_preserves_receipt_bytes_and_contexts(self):
        self.assertEqual(self.value["schema_version"], 2)
        self.assertEqual(decode_reader_output(self.raw), self.observation)
        self.assertEqual(encode_reader_output(decode_reader_output(self.raw)), self.raw)

    def test_legacy_version_one_round_trip_never_invents_receipt(self):
        raw = encode_reader_output(self.observation.packet)
        self.assertEqual(json.loads(raw)["schema_version"], 1)
        self.assertNotIn("site_receipt", json.loads(raw))
        self.assertEqual(decode_reader_output(raw), self.observation.packet)

    def test_versions_cannot_smuggle_omit_or_promote_receipt(self):
        missing = {k: v for k, v in self.value.items() if k != "site_receipt"}
        for value in ({**self.value, "schema_version": 1}, missing,
                      {**self.value, "schema_version": True},
                      {**self.value, "schema_version": 3},
                      {**self.value, "live_origin_verified": True}):
            with self.assertRaisesRegex(ValueError, "QWEN_READER_OUTPUT_INVALID"):
                decode_reader_output(json.dumps(value).encode())

    def test_changed_receipt_or_context_is_rejected_without_private_error_chain(self):
        receipt = {**self.value["site_receipt"], "capture_sha256": "0" * 64}
        context = {**self.value["after"], "evidence": ["d" * 64]}
        for value in ({**self.value, "site_receipt": receipt},
                      {**self.value, "after": context},
                      {**self.value, "site_receipt": {"private": "private-page"}}):
            with self.assertRaisesRegex(ValueError, "QWEN_READER_OUTPUT_INVALID") as caught:
                decode_reader_output(json.dumps(value).encode())
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("private-page", str(caught.exception))

    def test_encoder_rejects_tampered_packet_and_keeps_private_failures_fixed(self):
        bad = replace(self.observation, packet=replace(self.observation.packet, raw=b"private-page"))
        with self.assertRaisesRegex(ValueError, "QWEN_READER_PACKET_INVALID") as caught:
            encode_reader_output(bad)
        self.assertIsNone(caught.exception.__context__)

    def test_actual_process_preserves_receipt_and_journal_commits_it_atomically(self):
        result = record_qwen_read(self.f.journal, self.process(), event_id=self.f.event, expected_revision=0)
        self.assertEqual(result["raw"], self.f.raw)
        self.assertEqual(result["site_receipt"], self.value["site_receipt"])
        self.assertEqual(self.f.open().read_qwen_site_read(event_id=self.f.event), self.observation)
        self.assertFalse(result["live_origin_verified"])

    def test_replay_after_source_deleted_does_not_start_process(self):
        record_qwen_read(self.f.journal, self.process(), event_id=self.f.event, expected_revision=0)
        self.path.unlink()
        result = record_qwen_read(self.f.open(), self.process(), event_id=self.f.event, expected_revision=0)
        self.assertTrue(result["reused"])
        self.assertFalse(result["reader_invoked"])
        self.assertEqual(result["site_receipt"], self.value["site_receipt"])

    def test_actual_truncated_output_preserves_previously_committed_receipt(self):
        self.f.journal.append_qwen_site_read(self.observation, event_id=self.f.event, expected_revision=0)
        with self.assertRaisesRegex(ValueError, "QWEN_READ_FAILED"):
            record_qwen_read(self.f.journal, self.process("truncated"), event_id=uuid4(), expected_revision=1)
        self.assertEqual(self.f.open().resume()["revision"], 1)
        self.assertEqual(self.f.open().read_qwen_site_read(event_id=self.f.event), self.observation)

    def test_actual_partial_output_timeout_stops_child_without_committing_receipt(self):
        with self.assertRaisesRegex(ValueError, "QWEN_READ_FAILED"):
            record_qwen_read(self.f.journal, self.process("partial", timeout=5),
                             event_id=self.f.event, expected_revision=0)
        heartbeat = Path(str(self.path) + ".heartbeat")
        self.assertTrue(heartbeat.exists())
        before = heartbeat.read_bytes()
        time.sleep(0.2)
        self.assertEqual(heartbeat.read_bytes(), before)
        self.assertEqual(self.f.open().resume()["revision"], 0)

    def test_envelope_size_and_nonfinite_numbers_are_rejected(self):
        with patch("consilium.adapters.qwen_process_reader.MAX_READER_BYTES", len(self.raw) - 1):
            with self.assertRaisesRegex(ValueError, "QWEN_READER_OUTPUT_INVALID"):
                decode_reader_output(self.raw)
            with self.assertRaisesRegex(ValueError, "QWEN_READER_PACKET_INVALID"):
                encode_reader_output(self.observation)
        for constant in ("NaN", "Infinity", "-Infinity"):
            raw = self.raw.replace(b'"schema_version":2', b'"schema_version":' + constant.encode())
            with self.assertRaisesRegex(ValueError, "QWEN_READER_OUTPUT_INVALID") as caught:
                decode_reader_output(raw)
            self.assertIsNone(caught.exception.__context__)
