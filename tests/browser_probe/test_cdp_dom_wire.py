"""Raw DOM is private evidence and cannot be ingested as a Qwen response."""

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from consilium.adapters.cdp_dom_wire import decode_dom_output, encode_dom_output
from consilium.adapters.cdp_read_only import CdpDomObservation
from consilium.adapters.qwen_process_reader import decode_reader_output


class CdpDomWireTests(unittest.TestCase):
    def setUp(self):
        self.observation = CdpDomObservation("https://example.test/page", "tab-1", "frame-1", "loader-1", 2,
                                             '<div hidden>متن خصوصی\r\n<script>fake()</script></div>')
        self.raw = encode_dom_output(self.observation, selector="#answer")

    def decode(self, raw=None, selector="#answer"):
        return decode_dom_output(self.raw if raw is None else raw, selector=selector)

    def mutate(self, change):
        value = json.loads(self.raw)
        change(value)
        return json.dumps(value, ensure_ascii=False).encode()

    def test_exact_private_html_round_trip_no_visibility_claim(self):
        self.assertEqual(self.decode(), self.observation)
        self.assertIn("hidden", self.decode().outer_html)
        self.assertFalse(hasattr(self.decode(), "complete"))

    def test_raw_dom_rejected_by_qwen_packet_decoder(self):
        with self.assertRaisesRegex(ValueError, "QWEN_READER_OUTPUT_INVALID"):
            decode_reader_output(self.raw)

    def test_wrong_selector_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "CDP_DOM_OUTPUT_INVALID"):
            self.decode(selector="#other")

    def test_modified_html_or_hash_rejected(self):
        for change in (lambda v: v["observation"].update(outer_html="other"),
                       lambda v: v.update(html_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "CDP_DOM_OUTPUT_INVALID"):
                self.decode(self.mutate(change))

    def test_exact_version_kind_and_fields(self):
        for change in (lambda v: v.update(schema_version=True), lambda v: v.update(schema_version=1.0),
                       lambda v: v.update(schema_version=2), lambda v: v.update(kind="QWEN_RENDERED_TEXT_V1"),
                       lambda v: v.update(extra="secret"), lambda v: v["observation"].update(extra="secret")):
            with self.assertRaisesRegex(ValueError, "CDP_DOM_OUTPUT_INVALID"):
                self.decode(self.mutate(change))

    def test_identity_fields_and_node_types(self):
        for field, value in (("url", "http://example.test/page"), ("target_id", ""), ("frame_id", "\n"),
                             ("loader_id", None), ("node_id", True), ("node_id", 0), ("node_id", 2**31)):
            with self.assertRaisesRegex(ValueError, "CDP_DOM_PACKET_INVALID"):
                encode_dom_output(replace(self.observation, **{field: value}), selector="#answer")

    def test_empty_or_non_text_html_rejected(self):
        for html in ("", None, b"bytes"):
            with self.assertRaisesRegex(ValueError, "CDP_DOM_PACKET_INVALID"):
                encode_dom_output(replace(self.observation, outer_html=html), selector="#answer")

    def test_private_decode_error_has_no_context(self):
        with self.assertRaisesRegex(ValueError, "^CDP_DOM_OUTPUT_INVALID$") as caught:
            self.decode(b"private malformed document")
        self.assertIsNone(caught.exception.__context__)

    def test_duplicate_nonfinite_invalid_utf8_and_depth(self):
        for raw in (self.raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1'),
                    self.raw.replace(b'"node_id":2', b'"node_id":1e400'),
                    self.raw.replace(b'"node_id":2', b'"node_id":NaN'), b"\xff", b"[" * 65 + b"]" * 65):
            with self.assertRaisesRegex(ValueError, "CDP_DOM_OUTPUT_INVALID"):
                self.decode(raw)

    def test_input_byte_and_dom_byte_limits(self):
        with patch("consilium.adapters.cdp_dom_wire.MAX_MESSAGE_BYTES", len(self.raw) - 1), self.assertRaisesRegex(ValueError, "CDP_DOM_OUTPUT_INVALID"):
            self.decode()
        with patch("consilium.adapters.cdp_dom_wire.MAX_DOM_BYTES", 1), self.assertRaisesRegex(ValueError, "CDP_DOM_PACKET_INVALID"):
            encode_dom_output(self.observation, selector="#answer")

    def test_encoder_rejects_plain_dict(self):
        with self.assertRaisesRegex(ValueError, "CDP_DOM_PACKET_INVALID"):
            encode_dom_output({}, selector="#answer")

    def test_invalid_selector_contract_rejected(self):
        for selector in ("", "\n", None, "x" * 1025):
            with self.assertRaisesRegex(ValueError, "CDP_DOM_PACKET_INVALID"):
                encode_dom_output(self.observation, selector=selector)
