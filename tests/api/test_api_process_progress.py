"""Crash spool recovery is strict, bounded and context bound."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from consilium.adapters.api_codec import encode
from consilium.adapters.api_http import HttpGrant
from consilium.adapters.api_process_progress import ProgressWriter, read_progress
from consilium.core.contracts import FrozenInput, Message


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "response.frames"
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
            FrozenInput(messages=(Message(role="USER", content="x"),)),
        )
        self.attempt = uuid4()
        self.writer = ProgressWriter(self.path, self.grant, self.wire, self.attempt)

    def read(self):
        return read_progress(self.path, self.grant, self.wire, self.attempt)

    def test_first_chunk_and_unicode_are_exact_and_private(self):
        self.writer(200, "پاسخ".encode())
        self.writer(200, b"more")
        self.assertEqual(self.read().chunks, ("پاسخ".encode(), b"more"))
        self.assertTrue(self.read().interrupted)
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_torn_last_record_keeps_only_flushed_prefix(self):
        self.writer(200, b"first")
        with self.path.open("ab") as stream:
            stream.write(b'"unfinished')
        self.assertEqual(self.read().chunks, (b"first",))

    def test_complete_invalid_record_cannot_be_silently_skipped(self):
        self.writer(200, b"first")
        for bad in (b'"Zh=="\n', b"null\n", b'"%%%"\n', b'"\\ud800"\n'):
            original = self.path.read_bytes()
            self.path.write_bytes(original + bad)
            with self.assertRaises((ValueError, UnicodeError)):
                self.read()
            self.path.write_bytes(original)

    def test_wrong_attempt_grant_or_request_cannot_be_recovered(self):
        self.writer(200, b"first")
        cases = (
            (self.grant, self.wire, uuid4()),
            (replace(self.grant, account_binding_id=uuid4()), self.wire, self.attempt),
            (self.grant, replace(self.wire, body=b"other"), self.attempt),
            (self.grant, replace(self.wire, streaming=True), self.attempt),
        )
        for grant, wire, attempt in cases:
            with self.assertRaises(ValueError):
                read_progress(self.path, grant, wire, attempt)

    def test_boolean_version_or_status_rejected(self):
        self.writer(200, b"")
        header = json.loads(self.path.read_bytes())
        for field in (0, 4):
            bad = header.copy()
            bad[field] = True
            self.path.write_text(json.dumps(bad) + "\n")
            with self.assertRaises(ValueError):
                self.read()

    def test_empty_callbacks_do_not_expand_spool(self):
        self.writer(200, b"")
        before = self.path.read_bytes()
        for _ in range(100):
            self.writer(200, b"")
        self.assertEqual(self.path.read_bytes(), before)

    def test_status_cannot_change_midstream(self):
        self.writer(200, b"first")
        with self.assertRaises(ValueError):
            self.writer(429, b"second")
        self.assertEqual(self.read().chunks, (b"first",))

    def test_oversize_chunk_never_written(self):
        with self.assertRaises(ValueError):
            self.writer(200, b"x" * (1048576 + 1))
        self.assertFalse(self.path.exists())

    def test_existing_file_never_overwritten(self):
        self.path.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            self.writer(200, b"new")
        self.assertEqual(self.path.read_bytes(), b"existing")

    def test_symlink_never_read(self):
        other = self.path.with_name("other")
        other.write_bytes(b"private")
        self.path.symlink_to(other)
        with self.assertRaises(ValueError):
            self.read()

    def test_private_parse_failure_has_no_exception_context_or_body(self):
        self.path.write_bytes(b'{"private-response":"private content"\n')
        with self.assertRaisesRegex(ValueError, "^API_PROGRESS_INVALID$") as error:
            self.read()
        self.assertIsNone(error.exception.__context__)
        self.assertFalse(hasattr(error.exception, "doc"))

    def test_oversize_file_is_rejected_before_decoding(self):
        self.path.write_bytes(b"x" * (3 * 1048576 + 1))
        with self.assertRaisesRegex(ValueError, "^API_PROGRESS_INVALID$"):
            self.read()

    def test_decoded_body_bound_is_independent_of_file_bound(self):
        import base64

        self.writer(200, b"")
        with self.path.open("ab") as stream:
            stream.write(
                json.dumps(base64.b64encode(b"x" * (1048576 + 1)).decode()).encode()
                + b"\n"
            )
        with self.assertRaisesRegex(ValueError, "^API_PROGRESS_INVALID$"):
            self.read()

    def test_encoded_file_budget_rejects_append_and_preserves_prefix(self):
        from consilium.adapters.api_process_wire import MAX_PROCESS_BYTES

        self.writer(200, b"first")
        before = self.path.read_bytes()
        self.writer.file_size = MAX_PROCESS_BYTES - 2
        with self.assertRaisesRegex(ValueError, "^API_PROGRESS_INVALID$"):
            self.writer(200, b"second")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.read().chunks, (b"first",))
