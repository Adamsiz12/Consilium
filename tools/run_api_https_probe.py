#!/usr/bin/env python3
"""Optional real loopback TLS probe; openssl certificate, zero provider calls."""

import datetime as dt
import json
import os
import platform
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import qualityctl as q

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from consilium.adapters.api_codec import encode
from consilium.adapters.api_http import AccessBlocked, HttpGrant
from consilium.adapters.api_process import ApiProcessTransport
from consilium.core.contracts import FrozenInput, Message
from consilium.shell.bounded_read_process import BoundedCommandProcess


class LoopbackTlsProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="consilium-tls-probe-")
        cls.root = Path(cls.temp.name)
        cls.cert, cls.key = cls.root / "cert.pem", cls.root / "key.pem"
        subprocess.run(
            (
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=127.0.0.1",
                "-addext",
                "subjectAltName=IP:127.0.0.1",
                "-keyout",
                str(cls.key),
                "-out",
                str(cls.cert),
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
        cls.key.chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.received = []
        self.release = threading.Event()
        received, release = self.received, self.release

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                if (
                    not 0 < size <= 1048576
                    or self.headers.get("x-goog-api-key") != "synthetic-loopback-key"
                ):
                    self.send_error(400)
                    return
                received.append((self.path, self.rfile.read(size)))
                if self.path == "/quota":
                    self.send_response(429)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = {
                    "responseId": "loopback-1",
                    "candidates": [
                        {"content": {"role": "model", "parts": [{"text": "پاسخ محلی"}]}}
                    ],
                }
                if self.path in ("/success", "/finished"):
                    body["candidates"][0]["finishReason"] = "STOP"
                payload = json.dumps(body, ensure_ascii=False).encode()
                if self.path != "/success":
                    payload = b"data: " + payload + b"\n\n"
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/json"
                    if self.path == "/success"
                    else "text/event-stream",
                )
                self.send_header(
                    "Content-Length",
                    str(
                        len(payload) if self.path == "/success" else len(payload) + 100
                    ),
                )
                self.end_headers()
                self.wfile.write(payload)
                self.wfile.flush()
                if self.path != "/success":
                    release.wait(3)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, self.key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.02},
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.stop)
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
            FrozenInput(messages=(Message(role="USER", content="پرسش محلی"),)),
        )
        self.attempt = uuid4()

    def stop(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def send(self, mode, *, trusted=True):
        streaming = mode in ("partial", "finished")
        if streaming:
            self.wire = replace(self.wire, streaming=True)
            self.grant = replace(
                self.grant,
                endpoint=self.grant.endpoint.replace(
                    ":generateContent", ":streamGenerateContent?alt=sse"
                ),
            )
        self.transport = ApiProcessTransport(self.grant)
        endpoint = f"https://127.0.0.1:{self.server.server_port}/{mode}"

        def process(path, timeout, credentials):
            return BoundedCommandProcess(
                (
                    sys.executable,
                    str(ROOT / "tests/api/api_tls_fixture.py"),
                    str(path),
                    endpoint,
                ),
                timeout_seconds=timeout,
                credential_environment=credentials,
            )

        self.transport._process = process
        with patch.dict(
            os.environ,
            {
                "SSL_CERT_FILE": str(
                    self.cert if trusted else self.root / "untrusted.pem"
                ),
                "GEMINI_API_KEY": "synthetic-loopback-key",
            },
        ):
            result = self.transport.send(
                self.wire,
                attempt_id=self.attempt,
                timeout_seconds=1 if streaming else 3,
            )
            with self.assertRaises(AccessBlocked):
                self.transport.send(
                    self.wire, attempt_id=self.attempt, timeout_seconds=3
                )
        self.assertEqual(
            self.received, [("/" + mode, self.wire.body)] if trusted else []
        )
        return result

    def test_actual_tls_success_exact_wire_and_no_retry(self):
        result = self.send("success")
        self.assertEqual(result.code, "RESPONSE_COMPLETE")
        self.assertEqual(result.observation.content, "پاسخ محلی")
        self.assertIn(self.attempt, self.transport.frames)

    def test_actual_tls_partial_timeout_preserves_prefix(self):
        result = self.send("partial")
        self.assertEqual(result.code, "RESPONSE_PARTIAL")
        self.assertEqual(result.observation.content, "پاسخ محلی")
        self.assertTrue(self.transport.frames[self.attempt].interrupted)

    def test_actual_tls_finish_before_timeout_still_partial(self):
        result = self.send("finished")
        self.assertEqual(result.code, "RESPONSE_PARTIAL")
        self.assertEqual(result.observation.content, "پاسخ محلی")

    def test_actual_tls_quota_never_claims_unsent(self):
        result = self.send("quota")
        self.assertEqual((result.delivery, result.code), ("UNKNOWN_DELIVERY", "QUOTA"))

    def test_actual_tls_untrusted_certificate_blocks_before_http(self):
        result = self.send("success", trusted=False)
        self.assertEqual(
            (result.delivery, result.code),
            ("UNKNOWN_DELIVERY", "TRANSPORT_INTERRUPTED"),
        )
        self.assertNotIn(self.attempt, self.transport.frames)


def main():
    before = q.source_digest(ROOT)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(LoopbackTlsProbe)
    )
    after = q.source_digest(ROOT)
    report = {
        "scope": "REAL_LOOPBACK_TLS_AND_OWNED_PROCESS_NOT_PROVIDER_CERTIFICATION",
        "status": "PASS" if result.wasSuccessful() and before == after else "FAIL",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "source_digest_before": before,
        "source_digest_after": after,
        "date_utc": dt.datetime.now(dt.UTC).isoformat(),
        "host": {
            "system": platform.system(),
            "python": platform.python_version(),
            "ssl": ssl.OPENSSL_VERSION,
        },
        "provider_calls": 0,
        "real_credentials_used": False,
        "phase_accepted": False,
        "windows_execution": "NOT_RUN" if os.name != "nt" else "THIS_RUN",
    }
    folder = ROOT / "evidence/api-https-probe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "RUN.json").write_bytes(q.encoded(report))
    print(json.dumps(report))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
