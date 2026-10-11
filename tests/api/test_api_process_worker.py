"""CLI rejects untrusted private config before any live exchange."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from consilium.adapters.api_codec import encode
from consilium.adapters.api_http import HttpFrames, HttpGrant
from consilium.adapters.api_process_wire import (
    decode_process_outcome,
    encode_process_request,
)
from consilium.core.contracts import FrozenInput, Message
from consilium.shell.api_process_worker import execute, main


class WorkerTests(unittest.TestCase):
    def setUp(self):
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
            FrozenInput(messages=(Message(role="USER", content="private prompt"),)),
        )
        self.attempt = uuid4()
        self.raw = encode_process_request(self.grant, self.wire, self.attempt, 1)

    def test_execute_injected_exchange_is_one_call_and_bound(self):
        calls = []

        def exchange(*args):
            calls.append(args)
            return HttpFrames(429, ())

        with patch.dict(os.environ, {"GEMINI_API_KEY": "synthetic-key"}):
            raw = execute(self.raw, http=exchange)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            decode_process_outcome(raw, self.grant, self.wire, self.attempt).code,
            "QUOTA",
        )
        self.assertNotIn(b"synthetic-key", raw)

    def test_invalid_input_fixed_error_without_exception_context(self):
        with self.assertRaises(ValueError) as error:
            execute(b'{"private": "private prompt"}')
        self.assertEqual(str(error.exception), "API_PROCESS_EXECUTION_FAILED")
        self.assertIsNone(error.exception.__context__)

    def test_missing_key_blocks_injected_exchange(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("consilium.shell.api_process_worker.https_once") as exchange,
            self.assertRaises(ValueError),
        ):
            execute(self.raw, http=exchange)
        exchange.assert_not_called()

    def test_cli_does_not_accept_executable_or_injected_exchange(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(main(["config", "--http=other"]), 2)
        self.assertEqual(stderr.getvalue(), "API_PROCESS_REQUIRES_PRIVATE_REQUEST\n")

    def test_actual_cli_disabled_config_never_emits_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            value = json.loads(self.raw)
            value["grant"]["enabled"] = False
            path.write_text(json.dumps(value))
            result = subprocess.run(
                (sys.executable, "-m", "consilium.shell.api_process_worker", str(path)),
                capture_output=True,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
                ),
                timeout=3,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(result.stderr, b"API_PROCESS_EXECUTION_FAILED\n")
            self.assertFalse(path.with_name("response.frames").exists())

    def test_actual_cli_missing_file_fixed_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "consilium.shell.api_process_worker",
                    str(Path(directory) / "missing"),
                ),
                capture_output=True,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
                ),
                timeout=3,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"API_PROCESS_EXECUTION_FAILED\n")
