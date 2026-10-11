"""Synthetic surface gates; no test establishes live acquisition provenance."""

import unittest
from dataclasses import replace
from uuid import uuid4

import test_qwen_capture_journal

from consilium.adapters.qwen_site_reader import (
    QwenSiteRead,
    QwenSiteReader,
    QwenSiteReceipt,
    QwenSurface,
    QwenSurfaceCapture,
    verify_site_receipt,
)
from consilium.shell.qwen_capture_ingest import record_qwen_read

URL = "https://example.test/conversation/fixture"


class Source:
    def __init__(self, surface, raw):
        self.before = self.after = surface
        self.capture = QwenSurfaceCapture(surface, raw)
        self.calls = []

    def read_surface(self):
        self.calls.append("surface")
        return self.before if len(self.calls) == 1 else self.after

    def read_capture(self):
        self.calls.append("capture")
        return self.capture


class QwenSiteReaderTests(unittest.TestCase):
    def setUp(self):
        self.f = test_qwen_capture_journal.QwenCaptureJournalTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.surface = QwenSurface(URL, "tab-1", "document-1", self.f.f.f.context)
        self.source = Source(self.surface, self.f.raw)

    def reader(self):
        return QwenSiteReader(self.source, expected_url=URL, expected_tab_id="tab-1")

    def test_order_exact_bytes_and_replay_without_reobserving(self):
        result = record_qwen_read(self.f.journal, self.reader(), event_id=self.f.event, expected_revision=0)
        self.assertEqual(self.source.calls, ["surface", "capture", "surface"])
        self.assertEqual(result["raw"], self.f.raw)
        self.assertFalse(result["live_origin_verified"])
        result = record_qwen_read(self.f.open(), self.reader(), event_id=self.f.event, expected_revision=0)
        self.assertTrue(result["reused"])
        self.assertEqual(len(self.source.calls), 3)

    def test_wrong_initial_url_or_tab_stops_before_capture(self):
        for change in ({"url": "https://other.test/"}, {"tab_id": "other"}):
            self.source = Source(replace(self.surface, **change), self.f.raw)
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_READ_FAILED"):
                self.reader()()
            self.assertEqual(self.source.calls, ["surface"])

    def test_capture_document_or_identity_drift_stops_before_after_read(self):
        context = self.surface.context.model_copy(update={"model_id": "other"})
        for change in ({"document_id": "new"}, {"context": context}, {"tab_id": "other"}):
            self.source = Source(self.surface, self.f.raw)
            self.source.capture = replace(self.source.capture, surface=replace(self.surface, **change))
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_READ_FAILED"):
                self.reader()()
            self.assertEqual(self.source.calls, ["surface", "capture"])

    def test_after_navigation_or_context_change_preserves_committed_capture(self):
        self.f.append()
        context = self.surface.context.model_copy(update={"account_binding_id": uuid4()})
        for change in ({"url": "https://other.test/"}, {"document_id": "new"}, {"context": context}):
            self.source = Source(self.surface, self.f.raw)
            self.source.after = replace(self.surface, **change)
            with self.assertRaisesRegex(ValueError, "QWEN_READ_FAILED"):
                record_qwen_read(self.f.journal, self.reader(), event_id=uuid4(), expected_revision=1)
            self.assertEqual(self.f.open().resume()["revision"], 1)
            self.assertEqual(self.f.open().read_qwen_capture(event_id=self.f.event)["raw"], self.f.raw)

    def test_invalid_or_mismatched_capture_rejected_before_after_read(self):
        for raw in (b"private broken JSON", self.f.raw.replace(
            self.surface.context.model_id.encode(), b"other-model"
        )):
            self.source = Source(self.surface, raw)
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_READ_FAILED") as caught:
                self.reader()()
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(self.source.calls, ["surface", "capture"])

    def test_source_exception_is_private_at_each_observation(self):
        for position in range(3):
            self.source = Source(self.surface, self.f.raw)
            def fail():
                raise RuntimeError("private-page-and-session")
            if position == 1:
                self.source.read_capture = fail
            elif position == 0:
                self.source.read_surface = fail
            else:
                original = self.source.read_surface
                def after_failure(original=original):
                    if self.source.calls:
                        return fail()
                    return original()
                self.source.read_surface = after_failure
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_READ_FAILED") as caught:
                self.reader()()
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("private-page", str(caught.exception))

    def test_unsafe_configuration_rejected_without_observation(self):
        for url in ("http://example.test/", "https://user:secret@example.test/",
                    "https://example.test/?token=secret", "https://example.test/#secret",
                    "https://example.test:bad/", "https://example.test:443/",
                    "https://example.test/\n", "https://example.test\\other/"):
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_CONFIGURATION_INVALID") as caught:
                QwenSiteReader(self.source, expected_url=url, expected_tab_id="tab-1")
            self.assertIsNone(caught.exception.__context__)
        self.assertEqual(self.source.calls, [])

    def test_signed_out_or_missing_document_rejected_before_capture(self):
        context = self.surface.context.model_copy(update={"authentication": "SIGNED_OUT"})
        for change in ({"context": context}, {"document_id": ""}):
            self.source = Source(replace(self.surface, **change), self.f.raw)
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_READ_FAILED"):
                self.reader()()
            self.assertEqual(self.source.calls, ["surface"])

    def test_bounded_metadata_configuration_rejected_without_read(self):
        for tab_id in ("x" * 257, "tab\nprivate", "tab\0private", 1, None):
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_CONFIGURATION_INVALID"):
                QwenSiteReader(self.source, expected_url=URL, expected_tab_id=tab_id)
        with self.assertRaisesRegex(ValueError, "QWEN_SITE_CONFIGURATION_INVALID"):
            QwenSiteReader(self.source, expected_url=URL + "x" * 8192, expected_tab_id="tab-1")
        self.assertEqual(self.source.calls, [])

    def test_invalid_document_metadata_preserves_existing_journal(self):
        self.f.append()
        for document_id in ("x" * 257, "doc\nprivate", "doc\0private", 1, None):
            self.source = Source(replace(self.surface, document_id=document_id), self.f.raw)
            with self.assertRaisesRegex(ValueError, "QWEN_READ_FAILED"):
                record_qwen_read(self.f.journal, self.reader(), event_id=uuid4(), expected_revision=1)
            self.assertEqual(self.source.calls, ["surface"])
            self.assertEqual(self.f.open().resume()["revision"], 1)

    def test_comparison_objects_cannot_impersonate_url_or_tab(self):
        class EqualToAnything:
            def __eq__(self, other):
                return True
        for field in ("url", "tab_id"):
            self.source = Source(replace(self.surface, **{field: EqualToAnything()}), self.f.raw)
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_READ_FAILED"):
                self.reader()()
            self.assertEqual(self.source.calls, ["surface"])

    def test_receipt_binds_exact_bytes_and_separate_context_evidence_without_reread(self):
        self.source.after = replace(self.surface, context=self.surface.context.model_copy(
            update={"evidence": ("d" * 64,)}
        ))
        result = self.reader().read_with_receipt()
        self.assertEqual(self.source.calls, ["surface", "capture", "surface"])
        self.assertEqual(result.packet.raw, self.f.raw)
        self.assertNotEqual(result.receipt.before_context_sha256, result.receipt.after_context_sha256)
        self.assertEqual(verify_site_receipt(result), result.receipt)
        serialized = result.receipt.model_dump_json()
        self.assertNotIn(URL, serialized)
        self.assertNotIn("document-1", serialized)
        self.assertNotIn("live_origin_verified", serialized)
        self.assertEqual(QwenSiteReceipt.model_validate_json(serialized), result.receipt)

    def test_receipt_rejects_changed_bytes_or_context_even_when_identity_matches(self):
        result = self.reader().read_with_receipt()
        changed = result.packet.after.model_copy(update={"evidence": ("b" * 64,)})
        for packet in (replace(result.packet, raw=result.packet.raw + b" "),
                       replace(result.packet, after=changed)):
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_RECEIPT_INVALID") as caught:
                verify_site_receipt(replace(result, packet=packet))
            self.assertIsNone(caught.exception.__context__)
        self.assertEqual(len(self.source.calls), 3)

    def test_surface_receipt_changes_when_document_changes_between_acquisitions(self):
        first = self.reader().read_with_receipt()
        self.source = Source(replace(self.surface, document_id="document-2"), self.f.raw)
        second = self.reader().read_with_receipt()
        self.assertNotEqual(first.receipt.surface_sha256, second.receipt.surface_sha256)
        self.assertEqual(first.receipt.capture_sha256, second.receipt.capture_sha256)

    def test_receipt_does_not_accept_authority_fields_or_private_invalid_packet(self):
        result = self.reader().read_with_receipt()
        with self.assertRaises(ValueError):
            QwenSiteReceipt.model_validate({**result.receipt.model_dump(), "live_origin_verified": True})
        for value in (None, QwenSiteRead(replace(result.packet, raw=b"private-page"), result.receipt)):
            with self.assertRaisesRegex(ValueError, "QWEN_SITE_RECEIPT_INVALID") as caught:
                verify_site_receipt(value)
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("private-page", str(caught.exception))
