"""Actual owned processes, exclusively fake exchanges with dummy credentials."""

import os
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from consilium.adapters.api_codec import encode
from consilium.adapters.api_http import AccessBlocked, HttpGrant
from consilium.adapters.api_process import ApiProcessTransport
from consilium.core.contracts import FrozenInput, Message
from consilium.shell.bounded_read_process import BoundedCommandProcess

FIXTURE = Path(__file__).with_name("api_process_fixture.py")


class ApiProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.marker = self.root / "fake-send-marker"
        self.grant = HttpGrant(
            "google",
            "fixture-model",
            uuid4(),
            uuid4(),
            "https://generativelanguage.googleapis.com/v1beta/models/fixture-model:generateContent",
            "GEMINI_API_KEY",
            True,
            True,
        )
        self.wire = encode(
            "google",
            "fixture-model",
            FrozenInput(messages=(Message(role="USER", content="private prompt"),)),
        )
        self.attempt = uuid4()
        self.transport = ApiProcessTransport(self.grant)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"GEMINI_API_KEY": "synthetic-pinned-key"}).start()
        self.paths = []

    def fixture(self, mode="success", change_environment=False):
        def process(path, timeout, credential_environment):
            self.paths.append(path)
            self.assertNotIn(b"synthetic-pinned-key", path.read_bytes())
            self.assertEqual(
                credential_environment, {"GEMINI_API_KEY": "synthetic-pinned-key"}
            )
            if change_environment:
                os.environ["GEMINI_API_KEY"] = "changed-outside-child"
            return BoundedCommandProcess(
                (sys.executable, str(FIXTURE), mode, str(path), str(self.marker)),
                timeout_seconds=timeout,
                credential_environment=credential_environment,
            )

        self.transport._process = process

    def send(self, timeout=5):
        return self.transport.send(
            self.wire, attempt_id=self.attempt, timeout_seconds=timeout
        )

    def test_actual_success_exact_private_response_and_config_cleanup(self):
        self.fixture()
        result = self.send()
        self.assertEqual(
            (result.delivery, result.code, result.observation.content),
            ("CONFIRMED_DELIVERY", "RESPONSE_COMPLETE", "پاسخ"),
        )
        self.assertEqual(self.marker.read_bytes(), b"X")
        self.assertFalse(self.paths[0].exists())
        self.assertNotIn("synthetic-pinned-key", repr(result))

    def test_actual_quota_is_unknown_without_retry(self):
        self.fixture("quota")
        result = self.send()
        self.assertEqual((result.delivery, result.code), ("UNKNOWN_DELIVERY", "QUOTA"))
        with self.assertRaisesRegex(AccessBlocked, "INVALID_OR_REPEATED_ATTEMPT"):
            self.send()
        self.assertEqual(self.marker.read_bytes(), b"X")

    def test_actual_truncated_or_wrong_context_is_unknown_and_reserved(self):
        for mode in ("truncated", "wrong-context"):
            self.attempt = uuid4()
            self.fixture(mode)
            result = self.send()
            self.assertEqual(
                (result.delivery, result.code),
                ("UNKNOWN_DELIVERY", "TRANSPORT_INTERRUPTED"),
            )
            with self.assertRaises(AccessBlocked):
                self.send()
        self.assertEqual(self.marker.read_bytes(), b"XX")

    def test_actual_timeout_stops_owned_descendant_and_never_retries(self):
        self.fixture("hang")
        result = self.send(timeout=1)
        self.assertEqual(
            (result.delivery, result.code),
            ("UNKNOWN_DELIVERY", "TRANSPORT_INTERRUPTED"),
        )
        heartbeat = Path(str(self.marker) + ".heartbeat")
        self.assertTrue(heartbeat.exists())
        before = heartbeat.read_bytes()
        time.sleep(0.15)
        self.assertEqual(heartbeat.read_bytes(), before)
        with self.assertRaises(AccessBlocked):
            self.send()
        self.assertEqual(self.marker.read_bytes(), b"X")
        self.assertFalse(self.paths[0].exists())

    def test_actual_child_credential_is_pinned_despite_parent_environment_change(self):
        self.fixture(change_environment=True)
        self.assertEqual(self.send().code, "RESPONSE_COMPLETE")
        self.assertEqual(os.environ["GEMINI_API_KEY"], "changed-outside-child")

    def test_disabled_or_wrong_grant_never_spawns(self):
        for grant in (
            replace(self.grant, enabled=False),
            replace(self.grant, free_only_confirmed=False),
            replace(self.grant, model="other"),
        ):
            transport = ApiProcessTransport(grant)
            with (
                patch.object(transport, "_process") as process,
                self.assertRaises(AccessBlocked),
            ):
                transport.send(self.wire, attempt_id=uuid4(), timeout_seconds=1)
            process.assert_not_called()

    def test_missing_key_never_reserves_or_spawns(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(self.transport, "_process") as process,
            self.assertRaisesRegex(AccessBlocked, "CREDENTIAL_UNAVAILABLE"),
        ):
            self.send()
        process.assert_not_called()
        self.assertEqual(self.transport._attempts, set())

    def test_invalid_attempt_or_budget_never_spawns(self):
        for timeout in (True, 0, 901, float("nan")):
            with (
                patch.object(self.transport, "_process") as process,
                self.assertRaises(AccessBlocked),
            ):
                self.send(timeout)
            process.assert_not_called()
        with self.assertRaises(AccessBlocked):
            self.transport.send(self.wire, attempt_id="wrong", timeout_seconds=1)

    def test_process_factory_failure_is_private_unknown_and_not_retried(self):
        with patch.object(
            self.transport, "_process", side_effect=RuntimeError("private credential")
        ) as process:
            result = self.send()
            self.assertEqual(result.code, "TRANSPORT_INTERRUPTED")
            with self.assertRaises(AccessBlocked):
                self.send()
        process.assert_called_once()

    def test_packaged_command_and_pinned_environment(self):
        process = self.transport._process(
            Path("private.json"), 900, {"GEMINI_API_KEY": "synthetic-pinned-key"}
        )
        self.assertEqual(
            process.command,
            (
                sys.executable,
                "-m",
                "consilium.shell.api_process_worker",
                "private.json",
            ),
        )
        self.assertEqual(process.timeout_seconds, 900)
        self.assertNotIn("synthetic-pinned-key", repr(process.command))

    def test_generic_credential_environment_rejects_system_overrides(self):
        for values in (
            {"HOME": "other"},
            {"PYTHONPATH": "injection"},
            {"GEMINI_API_KEY": b"bytes"},
            {"GEMINI_API_KEY": "x\0"},
        ):
            with self.assertRaisesRegex(
                ValueError, "BOUNDED_COMMAND_CONFIGURATION_INVALID"
            ):
                BoundedCommandProcess((sys.executable,), credential_environment=values)

    def test_timeout_preserves_stream_prefix_without_completion_or_retry(self):
        self.wire = replace(self.wire, streaming=True)
        self.grant = replace(
            self.grant,
            endpoint=self.grant.endpoint.replace(
                ":generateContent", ":streamGenerateContent?alt=sse"
            ),
        )
        self.transport = ApiProcessTransport(self.grant)
        for mode in ("partial-hang", "finished-hang"):
            self.attempt = uuid4()
            self.fixture(mode)
            result = self.send(timeout=1)
            self.assertEqual(result.code, "RESPONSE_PARTIAL")
            self.assertEqual(result.observation.content, "پاسخ جزئی")
            self.assertTrue(self.transport.frames[self.attempt].interrupted)
            self.assertIn(
                "پاسخ جزئی".encode(),
                b"".join(self.transport.frames[self.attempt].chunks),
            )
            with self.assertRaises(AccessBlocked):
                self.send()
        self.assertEqual(self.marker.read_bytes(), b"XX")

    def test_concurrent_same_attempt_spawns_once(self):
        entered, release = threading.Event(), threading.Event()
        results = []

        def process(*_args):
            entered.set()
            release.wait(2)
            raise OSError("synthetic unavailable process")

        self.transport._process = process
        thread = threading.Thread(target=lambda: results.append(self.send()))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(AccessBlocked):
                self.send()
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "TRANSPORT_INTERRUPTED")

    def test_unrelated_provider_credential_is_not_inherited(self):
        self.fixture()
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "unrelated-synthetic-key"}):
            self.assertEqual(self.send().code, "RESPONSE_COMPLETE")

    def test_qwen_real_process_uses_only_bound_provider_key(self):
        self.grant = HttpGrant(
            "qwen",
            "fixture-model",
            uuid4(),
            uuid4(),
            "https://workspace-123.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
            "DASHSCOPE_API_KEY",
            True,
            True,
        )
        self.wire = encode(
            "qwen",
            "fixture-model",
            FrozenInput(messages=(Message(role="USER", content="private prompt"),)),
        )
        self.transport = ApiProcessTransport(self.grant)

        def process(path, timeout, credentials):
            self.assertEqual(credentials, {"DASHSCOPE_API_KEY": "synthetic-pinned-key"})
            return BoundedCommandProcess(
                (sys.executable, str(FIXTURE), "success", str(path), str(self.marker)),
                timeout_seconds=timeout,
                credential_environment=credentials,
            )

        self.transport._process = process
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "synthetic-pinned-key"}):
            self.assertEqual(self.send().code, "RESPONSE_COMPLETE")

    def test_timeout_retains_nonstream_bytes_without_claiming_complete(self):
        self.fixture("finished-hang")
        result = self.send(timeout=1)
        self.assertEqual(
            (result.delivery, result.code), ("UNKNOWN_DELIVERY", "RESPONSE_NONE")
        )
        self.assertIsNone(result.observation.content)
        frames = self.transport.frames[self.attempt]
        self.assertTrue(frames.interrupted)
        self.assertIn("پاسخ جزئی".encode(), b"".join(frames.chunks))
        with self.assertRaises(AccessBlocked):
            self.send()
