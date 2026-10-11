"""Atomic declared site receipts, including real process commit-boundary exits."""

import json
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import test_qwen_capture_journal
import test_qwen_site_reader

from consilium.adapters.qwen_site_reader import QwenSiteReader
from consilium.shell.browser_watch_journal import digest, encoded
from consilium.shell.qwen_capture_ingest import record_qwen_read
from consilium.shell.qwen_site_journal import site_event, site_read_from_event


class QwenSiteJournalTests(unittest.TestCase):
    def setUp(self):
        self.f = test_qwen_capture_journal.QwenCaptureJournalTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        surface = test_qwen_site_reader.QwenSurface(
            test_qwen_site_reader.URL, "tab-1", "document-1", self.f.f.f.context
        )
        self.source = test_qwen_site_reader.Source(surface, self.f.raw)
        self.reader = QwenSiteReader(
            self.source, expected_url=surface.url, expected_tab_id=surface.tab_id
        )
        self.observation = self.reader.read_with_receipt()

    def append(self, observation=None, **changes):
        return self.f.journal.append_qwen_site_read(
            self.observation if observation is None else observation,
            event_id=changes.get("event_id", self.f.event),
            expected_revision=changes.get("expected_revision", 0),
        )

    def test_atomic_reopen_preserves_exact_packet_receipt_and_prior_format(self):
        self.append()
        journal = self.f.open()
        self.assertEqual(journal.read_qwen_site_read(event_id=self.f.event), self.observation)
        stored = journal.read_qwen_capture(event_id=self.f.event)
        self.assertEqual(stored["raw"], self.f.raw)
        self.assertEqual(stored["site_receipt"], self.observation.receipt.model_dump(mode="json"))
        self.assertFalse(stored["live_origin_verified"])
        self.assertEqual(journal.resume()["revision"], 1)

    def test_bridge_reuses_receipt_without_reading_source_again(self):
        self.source.calls.clear()
        result = record_qwen_read(self.f.journal, self.reader.read_with_receipt,
                                  event_id=self.f.event, expected_revision=0)
        self.assertEqual(len(self.source.calls), 3)
        self.assertIn("site_receipt", result)
        replay = record_qwen_read(self.f.open(), self.reader.read_with_receipt,
                                  event_id=self.f.event, expected_revision=0)
        self.assertTrue(replay["reused"])
        self.assertFalse(replay["reader_invoked"])
        self.assertEqual(replay["site_receipt"], result["site_receipt"])
        self.assertEqual(len(self.source.calls), 3)

    def test_exact_duplicate_is_idempotent_but_changed_receipt_conflicts(self):
        self.append()
        self.assertEqual(self.append(), 1)
        changed = replace(self.observation, receipt=self.observation.receipt.model_copy(
            update={"surface_sha256": "b" * 64}
        ))
        with self.assertRaisesRegex(ValueError, "JOURNAL_EVENT_ID_REUSED"):
            self.append(changed)
        self.assertEqual(self.f.open().read_qwen_site_read(event_id=self.f.event), self.observation)

    def test_invalid_receipt_or_stale_writer_preserves_existing_event(self):
        self.append()
        bad = replace(self.observation, packet=replace(
            self.observation.packet, raw=self.f.raw + b" "
        ))
        with self.assertRaisesRegex(ValueError, "QWEN_SITE_RECEIPT_INVALID"):
            self.append(bad, event_id=uuid4(), expected_revision=1)
        with self.assertRaisesRegex(ValueError, "JOURNAL_CLOSED_OR_STALE_REVISION"):
            self.append(event_id=uuid4(), expected_revision=0)
        self.assertEqual(self.f.open().resume()["revision"], 1)

    def test_receipt_mismatch_rejected_even_with_recomputed_outer_chain(self):
        self.append()
        with closing(sqlite3.connect(self.f.path)) as db, db:
            row = db.execute("SELECT revision,event_id,payload,parent_hash FROM events").fetchone()
            value = json.loads(row[2])
            value["site_receipt"]["capture_sha256"] = "0" * 64
            payload = encoded(value)
            checksum = digest(encoded([row[3], row[0], row[1], payload]))
            db.execute("UPDATE events SET payload=?,event_hash=?", (payload, checksum))
            db.execute("UPDATE header SET tip=?", (checksum,))
        with self.assertRaisesRegex(ValueError, "JOURNAL_QWEN_SITE_EVENT_INVALID") as caught:
            self.f.journal.read_qwen_capture(event_id=self.f.event)
        self.assertIsNone(caught.exception.__context__)

    def test_legacy_capture_is_readable_without_invented_receipt(self):
        self.f.append()
        self.assertNotIn("site_receipt", self.f.open().read_qwen_capture(event_id=self.f.event))
        with self.assertRaisesRegex(ValueError, "JOURNAL_QWEN_SITE_RECEIPT_NOT_FOUND"):
            self.f.open().read_qwen_site_read(event_id=self.f.event)

    def test_event_decoder_rejects_authority_fields_and_private_context_errors(self):
        value = site_event(self.observation)
        for changed in ({**value, "live_origin_verified": True},
                        {**value, "before": {"private": "private-page"}},
                        {**value, "reader_contract": "unsupported"}):
            with self.assertRaisesRegex(ValueError, "JOURNAL_QWEN_SITE_EVENT_INVALID") as caught:
                site_read_from_event(changed)
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("private-page", str(caught.exception))

    def crash(self, stage, code, revision):
        value = {**self.f.journal.spec, "event_id": str(self.f.event),
                 "site_event": site_event(self.observation)}
        config = self.f.root / "site-fixture.json"
        config.write_text(json.dumps(value), encoding="utf-8")
        worker = Path(__file__).with_name("browser_watch_crash_worker.py")
        result = subprocess.run([sys.executable, str(worker), str(self.f.path), str(config), stage],
                                capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, code, result.stderr.decode())
        journal = self.f.open()
        self.assertEqual(journal.resume()["revision"], revision)
        if revision:
            self.assertEqual(journal.read_qwen_site_read(event_id=self.f.event), self.observation)
        else:
            with self.assertRaisesRegex(ValueError, "JOURNAL_QWEN_CAPTURE_NOT_FOUND"):
                journal.read_qwen_site_read(event_id=self.f.event)

    def test_actual_process_exit_before_site_commit_rolls_back_packet_and_receipt(self):
        self.crash("before", 73, 0)

    def test_actual_process_exit_after_site_commit_recovers_packet_and_receipt(self):
        self.crash("after", 74, 1)
