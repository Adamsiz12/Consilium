"""Fake HTTP exchange verifies runtime gates without a real key or network."""

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from test_api_codec import envelope, raw

from consilium.adapters.api_codec import encode
from consilium.adapters.api_http import (
    AccessBlocked,
    ApiHttpTransport,
    HttpFrames,
    HttpGrant,
    Secret,
)
from consilium.core.contracts import FrozenInput, Message


class ApiHttpTests(unittest.TestCase):
    def setUp(self):
        self.wire = encode(
            "google",
            "fixture-model",
            FrozenInput(messages=(Message(role="USER", content="question"),)),
        )
        self.grant = HttpGrant(
            "google",
            "fixture-model",
            uuid4(),
            uuid4(),
            "https://generativelanguage.googleapis.com/v1beta/models/fixture-model:generateContent",
            "GEMINI_API_KEY",
            free_only_confirmed=True,
            enabled=True,
        )
        self.calls = []

    def http(self, *args):
        self.calls.append(args)
        return HttpFrames(200, (raw(envelope("google")),))

    def test_default_disabled_and_missing_key_block_before_http(self):
        from dataclasses import replace

        for grant in (
            replace(self.grant, enabled=False),
            replace(self.grant, free_only_confirmed=False),
        ):
            transport = ApiHttpTransport(grant, self.http)
            with self.assertRaises(AccessBlocked):
                transport.send(self.wire, attempt_id=uuid4(), timeout_seconds=1.0)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(AccessBlocked):
            ApiHttpTransport(self.grant, self.http).send(
                self.wire, attempt_id=uuid4(), timeout_seconds=1.0
            )
        self.assertEqual(self.calls, [])

    def test_wrong_models_credentials_endpoints_and_query_keys_rejected(self):
        from dataclasses import replace

        for changes in (
            {"model": "other"},
            {"credential_env": "OTHER_KEY"},
            {
                "endpoint": "http://generativelanguage.googleapis.com/v1beta/models/fixture-model:generateContent"
            },
            {"endpoint": self.grant.endpoint + "?key=secret"},
            {"endpoint": self.grant.endpoint.replace("googleapis.com", "evil.example")},
            {"endpoint": self.grant.endpoint + "#fragment"},
        ):
            with self.assertRaises(AccessBlocked):
                ApiHttpTransport(replace(self.grant, **changes), self.http).send(
                    self.wire, attempt_id=uuid4(), timeout_seconds=1.0
                )
        self.assertEqual(self.calls, [])

    def test_auth_header_redacted_success_and_duplicate_blocked(self):
        transport = ApiHttpTransport(self.grant, self.http)
        attempt = uuid4()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-secret"}):
            result = transport.send(self.wire, attempt_id=attempt, timeout_seconds=1.0)
            self.assertEqual(result.observation.state, "COMPLETE")
            with self.assertRaises(AccessBlocked):
                transport.send(self.wire, attempt_id=attempt, timeout_seconds=1.0)
        headers = self.calls[0][1]
        self.assertIsInstance(headers["x-goog-api-key"], Secret)
        self.assertNotIn("offline-test-secret", repr(headers))
        self.assertNotIn("offline-test-secret", repr(result))
        self.assertEqual(len(self.calls), 1)

    def test_transport_exception_drops_secret_error_and_never_retries(self):
        def fail(*args):
            raise RuntimeError("offline-test-secret")

        transport = ApiHttpTransport(self.grant, fail)
        attempt = uuid4()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-secret"}):
            result = transport.send(self.wire, attempt_id=attempt, timeout_seconds=1.0)
            self.assertEqual(result.delivery, "UNKNOWN_DELIVERY")
            self.assertNotIn("secret", repr(result))
            with self.assertRaises(AccessBlocked):
                transport.send(self.wire, attempt_id=attempt, timeout_seconds=1.0)

    def test_errors_and_bad_frames_do_not_claim_unsent_or_complete(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only"}):
            for frames in (
                HttpFrames(401, (b"secret",)),
                HttpFrames(429, ()),
                HttpFrames(500, ()),
                HttpFrames(200, (b"{secret",)),
                HttpFrames(200, (b"x" * 1048577,)),
            ):
                result = ApiHttpTransport(
                    self.grant, lambda *args, value=frames: value
                ).send(self.wire, attempt_id=uuid4(), timeout_seconds=1.0)
                self.assertEqual(result.delivery, "UNKNOWN_DELIVERY")
                self.assertNotIn("secret", repr(result))

    def test_qwen_uses_region_bound_bearer_and_stream_partial(self):
        wire = encode(
            "qwen",
            "fixture-model",
            FrozenInput(messages=(Message(role="USER", content="q"),)),
            streaming=True,
        )
        grant = HttpGrant(
            "qwen",
            "fixture-model",
            uuid4(),
            uuid4(),
            "https://workspace-123.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
            "DASHSCOPE_API_KEY",
            True,
            True,
        )
        calls = []

        def http(*args):
            calls.append(args)
            return HttpFrames(
                200,
                (
                    b'data: {"id":"q-1","choices":[{"delta":{"content":"partial"}}]}\n\n',
                ),
                True,
            )

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "fake-key"}):
            result = ApiHttpTransport(grant, http).send(
                wire, attempt_id=uuid4(), timeout_seconds=1.0
            )
        self.assertEqual(result.observation.state, "PARTIAL")
        self.assertEqual(calls[0][1]["Authorization"].reveal(), "Bearer fake-key")
        self.assertNotIn("fake-key", repr(calls[0][1]))

    def test_https_transport_closes_connection_never_follows_redirect_and_bounds_body(
        self,
    ):
        from consilium.adapters.api_http import https_once

        calls = []

        class Socket:
            def settimeout(self, value):
                calls.append(("timeout", value))

        class Response:
            status = 302

            def __init__(self):
                self.remaining = b"private redirect body"

            def read1(self, n):
                chunk = self.remaining[:n]
                self.remaining = self.remaining[n:]
                return chunk

        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = Socket()
                calls.append(("connect-init", args))

            def connect(self):
                calls.append(("connect",))

            def request(self, *args, **kwargs):
                calls.append(("request", args))

            def getresponse(self):
                return Response()

            def close(self):
                calls.append(("closed",))

        with patch(
            "consilium.adapters.api_http.http.client.HTTPSConnection", Connection
        ):
            frames = https_once(
                self.grant.endpoint, {"x-goog-api-key": Secret("fake-key")}, b"{}", 1.0
            )
        self.assertEqual(frames.status, 302)
        self.assertFalse(frames.interrupted)
        self.assertEqual(sum(row[0] == "request" for row in calls), 1)
        self.assertEqual(calls[-1], ("closed",))

    def test_socket_failure_returns_unknown_and_does_not_leak_headers(self):
        from consilium.adapters.api_http import https_once

        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = None

            def connect(self):
                raise OSError("fake-key")

            def close(self):
                pass

        with patch(
            "consilium.adapters.api_http.http.client.HTTPSConnection", Connection
        ):
            frames = https_once(
                self.grant.endpoint, {"Authorization": Secret("fake-key")}, b"{}", 1.0
            )
        self.assertTrue(frames.interrupted)
        self.assertEqual(frames.status, 0)
        self.assertNotIn("fake-key", repr(frames))

    def test_concurrent_same_attempt_reservation_is_atomic(self):
        import threading

        entered, second_credential = threading.Event(), threading.Event()
        results, errors, credentials = [], [], []
        calls = []
        def credential(_grant):
            credentials.append(1)
            if len(credentials) == 1:
                entered.set()
                second_credential.wait(0.2)
            else:
                second_credential.set()
            return "synthetic-key"
        def exchange(*_args):
            calls.append(1)
            return HttpFrames(429, ())
        transport = ApiHttpTransport(self.grant, exchange)
        attempt = uuid4()
        def send():
            try:
                results.append(transport.send(self.wire, attempt_id=attempt, timeout_seconds=1))
            except AccessBlocked as error:
                errors.append(str(error))
        with patch("consilium.adapters.api_http.credential_value", credential):
            first = threading.Thread(target=send)
            second = threading.Thread(target=send)
            first.start()
            self.assertTrue(entered.wait(1))
            second.start()
            first.join(2)
            second.join(2)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual((len(calls), len(credentials), len(results)), (1, 1, 1))
        self.assertEqual(errors, ["INVALID_OR_REPEATED_ATTEMPT"])

    def test_invalid_status_and_empty_request_never_claim_http_success(self):
        from dataclasses import replace

        from consilium.adapters.api_http import outcome_from_frames
        for frames in (HttpFrames(-1, ()), HttpFrames(600, ()), HttpFrames(0, ()), HttpFrames(0, (b"unexpected",), True)):
            self.assertEqual(outcome_from_frames(self.wire, frames).code, "INVALID_HTTP_FRAMES")
        self.assertEqual(outcome_from_frames(self.wire, HttpFrames(0, (), True)).code, "TRANSPORT_INTERRUPTED")
        with self.assertRaises(AccessBlocked):
            self.grant.validate(replace(self.wire, body=b""))
