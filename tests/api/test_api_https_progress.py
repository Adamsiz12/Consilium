"""Packaged HTTP callbacks expose only bounded received bytes, never headers."""

import unittest
from unittest.mock import patch

from consilium.adapters.api_http import Secret, https_once


class HttpsProgressTests(unittest.TestCase):
    def exchange(self, events, *, callback=None, status=200, endpoint=None):
        self.calls = []
        calls = self.calls

        class Response:
            def read1(self, size):
                calls.append(("read", size))
                value = events.pop(0) if events else b""
                if isinstance(value, Exception):
                    raise value
                return value

        response = Response()
        response.status = status

        class Connection:
            sock = None

            def __init__(self, *args, **kwargs):
                calls.append(("destination", args, kwargs.get("port")))

            def connect(self):
                calls.append(("connect",))

            def request(self, *args, **kwargs):
                calls.append(("request",))

            def getresponse(self):
                return response

            def close(self):
                calls.append(("close",))

        with patch(
            "consilium.adapters.api_http.http.client.HTTPSConnection", Connection
        ):
            return https_once(
                endpoint
                or "https://generativelanguage.googleapis.com/v1beta/models/fixture:generateContent",
                {"x-goog-api-key": Secret("synthetic-key")},
                b"{}",
                1,
                on_progress=callback,
            )

    def test_header_precedes_exact_chunks_without_secret(self):
        progress = []
        frames = self.exchange(
            [b"first", "پاسخ".encode()], callback=lambda *args: progress.append(args)
        )
        self.assertEqual(
            progress, [(200, b""), (200, b"first"), (200, "پاسخ".encode())]
        )
        self.assertEqual(frames.chunks, (b"first", "پاسخ".encode()))
        self.assertFalse(frames.interrupted)
        self.assertNotIn("synthetic-key", repr(progress))
        self.assertEqual(self.calls[-1], ("close",))

    def test_socket_failure_after_prefix_keeps_received_bytes(self):
        progress = []
        frames = self.exchange(
            [b"first", OSError("private")], callback=lambda *args: progress.append(args)
        )
        self.assertEqual(frames.chunks, (b"first",))
        self.assertTrue(frames.interrupted)
        self.assertEqual(progress, [(200, b""), (200, b"first")])

    def test_spool_disk_failure_closes_without_retry(self):
        def fail(status, chunk):
            if chunk:
                raise OSError("private disk failure")

        frames = self.exchange([b"first", b"second"], callback=fail)
        self.assertTrue(frames.interrupted)
        self.assertEqual(frames.chunks, (b"first",))
        self.assertEqual(self.calls.count(("request",)), 1)
        self.assertEqual(self.calls[-1], ("close",))

    def test_oversize_chunk_is_not_exposed_to_callback(self):
        progress = []
        frames = self.exchange(
            [b"x" * (1048576 + 1)], callback=lambda *args: progress.append(args)
        )
        self.assertTrue(frames.interrupted)
        self.assertEqual(frames.chunks, ())
        self.assertEqual(progress, [(200, b"")])

    def test_redirect_status_is_preserved_without_second_request(self):
        progress = []
        frames = self.exchange(
            [b"redirect"], status=302, callback=lambda *args: progress.append(args)
        )
        self.assertEqual(frames.status, 302)
        self.assertEqual(progress, [(302, b""), (302, b"redirect")])
        self.assertEqual(self.calls.count(("request",)), 1)

    def test_explicit_tls_port_is_used(self):
        self.exchange([], endpoint="https://127.0.0.1:43123/fixture")
        self.assertIn(("destination", ("127.0.0.1",), 43123), self.calls)
