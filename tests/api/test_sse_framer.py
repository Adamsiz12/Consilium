"""SSE byte boundaries and provider completion; synthetic payloads only."""

import unittest

import test_api_codec as fixtures
from test_api_codec import envelope, raw

from consilium.adapters.api_codec import CodecError, StreamDecoder, decode
from consilium.adapters.sse_framer import SseFramer, SseFramingError


class SseFramerTests(unittest.TestCase):
    def frames(self, body, *, chunks=None):
        framer = SseFramer()
        result = []
        for chunk in chunks or [body]:
            result.extend(framer.feed(chunk))
        return result, framer

    def test_all_line_endings_preserve_multiline_data(self):
        for newline in (b"\n", b"\r", b"\r\n"):
            body = newline.join((b"data: first", b"data:second", b"", b""))
            result, framer = self.frames(body)
            self.assertEqual(result, [b"first\nsecond"])
            self.assertFalse(framer.pending)

    def test_every_two_chunk_boundary_and_one_byte_feed(self):
        body = b"\xef\xbb\xbfdata: " + "پاسخ فارسی".encode() + b"\r\n\r\n"
        for split in range(len(body) + 1):
            self.assertEqual(self.frames(body, chunks=[body[:split], body[split:]])[0], ["پاسخ فارسی".encode()])
        self.assertEqual(self.frames(body, chunks=[bytes([b]) for b in body])[0], ["پاسخ فارسی".encode()])

    def test_only_one_optional_space_removed(self):
        result, _framer = self.frames(b"data:  leading space\n\n")
        self.assertEqual(result, [b" leading space"])

    def test_comments_and_unknown_fields_do_not_emit_data(self):
        result, _framer = self.frames(b":comment\nretry: 0\nid: other\nevent: arbitrary\n\ndata:ok\n\n")
        self.assertEqual(result, [b"ok"])

    def test_empty_data_and_field_without_colon(self):
        self.assertEqual(self.frames(b"data\n\n")[0], [b""])
        self.assertEqual(self.frames(b"data:\ndata\n\n")[0], [b"\n"])

    def test_eof_never_emits_unterminated_event(self):
        for body in (b"data: answer", b"data: answer\n", b"data:\n"):
            result, framer = self.frames(body)
            self.assertEqual(result, [])
            self.assertTrue(framer.pending)

    def test_single_initial_bom_only(self):
        self.assertEqual(self.frames(b"\xef\xbb\xbfdata:ok\n\n")[0], [b"ok"])
        self.assertEqual(self.frames(b"\xef\xbb\xbf\xef\xbb\xbfdata:ok\n\n")[0], [])
        self.assertEqual(self.frames(b"\ndata:\xef\xbb\xbfok\n\n")[0], [b"\xef\xbb\xbfok"])

    def test_mixed_and_split_crlf_do_not_invent_empty_line(self):
        body = b"data:first\r\ndata:second\n\r"
        self.assertEqual(self.frames(body, chunks=[bytes([b]) for b in body])[0], [b"first\nsecond"])

    def test_invalid_utf8_private_error_and_failed_state(self):
        framer = SseFramer()
        with self.assertRaisesRegex(SseFramingError, "^STREAM_INVALID_UTF8$") as caught:
            list(framer.feed(b"data:private \xff\n\n"))
        self.assertIsNone(caught.exception.__context__)
        with self.assertRaisesRegex(SseFramingError, "STREAM_CLOSED_OR_TYPE"):
            list(framer.feed(b"data:ok\n\n"))

    def test_invalid_utf8_in_comment_rejected(self):
        with self.assertRaisesRegex(SseFramingError, "STREAM_INVALID_UTF8"):
            self.frames(b":private\xff\n\n")

    def test_bound_is_total_bytes_even_for_comments(self):
        framer = SseFramer(max_bytes=10)
        list(framer.feed(b":12345\n"))
        with self.assertRaisesRegex(SseFramingError, "STREAM_TOO_LARGE"):
            list(framer.feed(b":abc\n"))
        self.assertTrue(framer.failed)

    def test_exact_limit_and_input_type(self):
        for limit in (True, 0, 1048577, 1.0):
            with self.assertRaisesRegex(SseFramingError, "SSE_CONFIGURATION_INVALID"):
                SseFramer(max_bytes=limit)
        with self.assertRaisesRegex(SseFramingError, "STREAM_CLOSED_OR_TYPE"):
            list(SseFramer().feed("text"))


class ProviderSseBoundaryTests(unittest.TestCase):
    def body(self, provider):
        return fixtures.ApiCodecTests().stream_bytes(provider)

    def test_provider_streams_all_line_endings_with_bom_every_split(self):
        for provider in ("google", "qwen"):
            for newline in (b"\n", b"\r", b"\r\n"):
                body = b"\xef\xbb\xbf" + self.body(provider).replace(b"\n", newline)
                for split in range(len(body) + 1):
                    parser = StreamDecoder(provider)
                    parser.feed(body[:split])
                    parser.feed(body[split:])
                    self.assertEqual(parser.close().state, "COMPLETE", (provider, newline, split))

    def test_prior_text_retained_when_same_chunk_has_later_corruption(self):
        body = self.body("google") + b"data: \xff\n\n"
        parser = StreamDecoder("google")
        with self.assertRaisesRegex(CodecError, "STREAM_INVALID_UTF8") as caught:
            parser.feed(body)
        self.assertIsNone(caught.exception.__context__)
        result = parser.close()
        self.assertEqual(result.state, "PARTIAL")
        self.assertIsNotNone(result.content)

    def test_unterminated_utf8_and_event_cannot_complete(self):
        for tail in (b"data: never finished", b":\xc3", b"data:\n"):
            parser = StreamDecoder("google")
            parser.feed(self.body("google") + tail)
            self.assertEqual(parser.close().state, "PARTIAL")

    def test_faulted_stream_freezes_prior_partial_text(self):
        parser = StreamDecoder("google")
        with self.assertRaises(CodecError):
            parser.feed(self.body("google") + b"data: \xff\n")
        before = parser.text
        with self.assertRaisesRegex(CodecError, "STREAM_BROKEN"):
            parser.feed(self.body("google"))
        self.assertEqual(parser.text, before)

    def test_json_failure_drops_private_exception_context(self):
        with self.assertRaisesRegex(CodecError, "^INVALID_JSON$") as caught:
            decode("google", b"private invalid JSON")
        self.assertIsNone(caught.exception.__context__)
        obj = envelope("google")
        body = raw(obj).replace(b'"promptTokenCount": 4', b'"promptTokenCount": 1e400')
        with self.assertRaisesRegex(CodecError, "INVALID_JSON"):
            decode("google", body)

    def test_invalid_json_unicode_scalar_rejected_valid_pair_preserved(self):
        import json
        for provider in ("google", "qwen"):
            with self.assertRaisesRegex(CodecError, "INVALID_JSON"):
                decode(provider, json.dumps(envelope(provider, text="\ud800")).encode())
            self.assertEqual(decode(provider, json.dumps(envelope(provider, text="😀")).encode()).content, "😀")
