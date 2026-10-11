"""Pinned recorded input producer: local assertions, never live provenance."""

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import test_qwen_site_journal

from consilium.adapters.qwen_process_reader import (
    QwenProcessReader,
    decode_reader_output,
)
from consilium.shell.qwen_capture_ingest import record_qwen_read
from consilium.shell.qwen_saved_site_read import (
    MAX_CONTEXT_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_RECEIPT_BYTES,
    read_saved_site,
)


class QwenSavedSiteReadTests(unittest.TestCase):
    def setUp(self):
        fixture = test_qwen_site_journal.QwenSiteJournalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture.f
        self.observation = fixture.observation
        self.paths = [self.f.root / name for name in (
            "before.json", "capture.json", "after.json", "receipt.json", "manifest.json"
        )]
        self.paths[0].write_text(self.observation.packet.before.model_dump_json(), encoding="utf-8")
        self.paths[1].write_bytes(self.observation.packet.raw)
        self.paths[2].write_text(self.observation.packet.after.model_dump_json(), encoding="utf-8")
        self.paths[3].write_text(self.observation.receipt.model_dump_json(), encoding="utf-8")
        self.pin()
        self.command = (sys.executable, "-m", "consilium.shell.qwen_saved_site_read",
                        *(str(path) for path in self.paths))

    def pin(self):
        self.manifest = {"schema_version": 1, **{
            role + "_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            for role, path in zip(("before", "capture", "after", "receipt"), self.paths[:4], strict=True)
        }}
        self.paths[4].write_text(json.dumps(self.manifest), encoding="utf-8")

    def read(self):
        return read_saved_site(*self.paths)

    def reject(self):
        with self.assertRaisesRegex(ValueError, "QWEN_SAVED_SITE_INVALID") as caught:
            self.read()
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(self.f.open().resume()["revision"], 0)

    def invoke(self, arguments=None):
        return subprocess.run(self.command if arguments is None else arguments,
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                              check=False, shell=False,
                              env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src")))

    def test_pinned_file_assembly_preserves_exact_observation(self):
        self.assertEqual(self.read(), self.observation)

    def test_valid_cli_emits_wire_v2_without_private_surface_strings(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout)["schema_version"], 2)
        self.assertEqual(decode_reader_output(result.stdout), self.observation)
        self.assertNotIn(b"document-1", result.stdout)

    def test_manifest_version_is_exact_and_supported(self):
        for version in (True, 2, "1"):
            self.paths[4].write_text(json.dumps({**self.manifest, "schema_version": version}))
            self.reject()

    def test_manifest_unknown_authority_and_missing_fields_rejected(self):
        for value in ({**self.manifest, "live_origin_verified": True},
                      {k: v for k, v in self.manifest.items() if k != "receipt_sha256"}):
            self.paths[4].write_text(json.dumps(value))
            self.reject()

    def test_manifest_duplicate_keys_rejected(self):
        self.paths[4].write_bytes(b'{"schema_version":1,' + self.paths[4].read_bytes()[1:])
        self.reject()

    def test_manifest_nonfinite_numbers_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            self.paths[4].write_text('{"schema_version":' + constant + '}')
            self.reject()

    def test_empty_input_files_rejected(self):
        for path in self.paths:
            original = path.read_bytes()
            path.write_bytes(b"")
            self.reject()
            path.write_bytes(original)

    def test_oversized_manifest_and_receipt_rejected(self):
        for path, size in ((self.paths[4], MAX_MANIFEST_BYTES), (self.paths[3], MAX_RECEIPT_BYTES)):
            original = path.read_bytes()
            path.write_bytes(b"x" * (size + 1))
            self.reject()
            path.write_bytes(original)

    def test_oversized_context_rejected(self):
        self.paths[0].write_bytes(b"x" * (MAX_CONTEXT_BYTES + 1))
        self.reject()

    def test_deep_json_manifest_rejected(self):
        self.paths[4].write_bytes(b"[" * 70 + b"0" + b"]" * 70)
        self.reject()

    def test_changed_before_file_rejected_by_role_hash(self):
        self.paths[0].write_bytes(self.paths[0].read_bytes() + b" ")
        self.reject()

    def test_changed_capture_file_rejected_by_role_hash(self):
        self.paths[1].write_bytes(self.paths[1].read_bytes() + b" ")
        self.reject()

    def test_changed_after_file_rejected_by_role_hash(self):
        self.paths[2].write_bytes(self.paths[2].read_bytes() + b" ")
        self.reject()

    def test_changed_receipt_file_rejected_by_role_hash(self):
        self.paths[3].write_bytes(self.paths[3].read_bytes() + b" ")
        self.reject()

    def test_matching_manifest_cannot_legitimize_context_drift(self):
        changed = self.observation.packet.after.model_copy(update={"account_binding_id": uuid4()})
        self.paths[2].write_text(changed.model_dump_json())
        self.pin()
        self.reject()

    def test_manifest_change_during_assembly_rejected(self):
        from consilium.shell.qwen_saved_read import bounded_file
        calls = []
        def changing(path, limit):
            raw = bounded_file(path, limit)
            calls.append(path)
            if path == self.paths[4] and len(calls) > 1:
                return raw + b" "
            return raw
        with patch("consilium.shell.qwen_saved_site_read.bounded_file", side_effect=changing):
            self.reject()
        self.assertEqual(calls.count(self.paths[4]), 2)

    def test_missing_and_nonregular_inputs_rejected_without_wait(self):
        for invalid in (self.f.root, self.f.root / "missing-private-file"):
            paths = [*self.paths[:4], invalid]
            with self.assertRaisesRegex(ValueError, "QWEN_SAVED_SITE_INVALID"):
                read_saved_site(*paths)
        if os.name != "nt":
            pipe = self.f.root / "pipe"
            os.mkfifo(pipe)
            with self.assertRaisesRegex(ValueError, "QWEN_SAVED_SITE_INVALID"):
                read_saved_site(*self.paths[:4], pipe)
            link = self.f.root / "manifest-link"
            link.symlink_to(self.paths[4])
            with self.assertRaisesRegex(ValueError, "QWEN_SAVED_SITE_INVALID"):
                read_saved_site(*self.paths[:4], link)

    def test_cli_private_failure_emits_no_partial_stdout(self):
        self.paths[0].write_bytes(b"private-page-and-session")
        self.pin()
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr.strip(), b"QWEN_SAVED_SITE_INVALID")
        result = self.invoke(self.command[:-1])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")

    def test_actual_process_journal_ingest_leaves_files_unchanged(self):
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in self.paths]
        result = record_qwen_read(self.f.journal, QwenProcessReader(self.command),
                                  event_id=self.f.event, expected_revision=0)
        self.assertEqual(result["raw"], self.f.raw)
        self.assertEqual(self.f.open().read_qwen_site_read(event_id=self.f.event), self.observation)
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in self.paths], before)
        self.assertFalse(result["live_origin_verified"])

    def test_replay_after_all_inputs_deleted_never_reexecutes_producer(self):
        reader = QwenProcessReader(self.command)
        record_qwen_read(self.f.journal, reader, event_id=self.f.event, expected_revision=0)
        for path in self.paths:
            path.unlink()
        result = record_qwen_read(self.f.open(), reader, event_id=self.f.event, expected_revision=0)
        self.assertTrue(result["reused"])
        self.assertFalse(result["reader_invoked"])
        self.assertEqual(result["site_receipt"], self.observation.receipt.model_dump(mode="json"))
