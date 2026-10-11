"""Process binding and private CLI gates; no live endpoint is touched."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from consilium.adapters.cdp_dom_wire import encode_dom_output
from consilium.adapters.cdp_process_reader import CdpProcessDomReader
from consilium.adapters.cdp_read_only import CdpDomObservation
from consilium.shell.cdp_dom_read import main

CONFIG = {"endpoint": "ws://127.0.0.1:9222/devtools/page/tab-1", "target_id": "tab-1",
          "expected_url": "https://example.test/page", "selector": "#answer", "timeout_seconds": 10}


class CdpProcessReaderTests(unittest.TestCase):
    def setUp(self):
        self.observation = CdpDomObservation(CONFIG["expected_url"], "tab-1", "frame-1", "doc-1", 2, "<div>private</div>")
        self.raw = encode_dom_output(self.observation, selector=CONFIG["selector"])

    def test_packaged_command_private_config_and_cleanup(self):
        paths = []
        def run(process):
            self.assertEqual(process.command[1:3], ("-m", "consilium.shell.cdp_dom_read"))
            path = Path(process.command[3])
            paths.append(path)
            self.assertEqual(json.loads(path.read_text()), CONFIG)
            return self.raw
        with patch("consilium.adapters.cdp_process_reader.BoundedReadProcess.run", run):
            self.assertEqual(CdpProcessDomReader(**CONFIG)(), self.observation)
        self.assertFalse(paths[0].exists())

    def test_process_failure_private_and_not_retried(self):
        with patch("consilium.adapters.cdp_process_reader.BoundedReadProcess.run", side_effect=RuntimeError("private")) as run, self.assertRaisesRegex(ValueError, "^CDP_PROCESS_READ_FAILED$") as caught:
            CdpProcessDomReader(**CONFIG)()
        self.assertIsNone(caught.exception.__context__)
        run.assert_called_once()

    def test_process_output_binding_must_match_config(self):
        value = json.loads(self.raw)
        for field, value_change in (("target_id", "other"), ("url", "https://other.test/")):
            value["observation"][field] = value_change
            with patch("consilium.adapters.cdp_process_reader.BoundedReadProcess.run", return_value=json.dumps(value).encode()), self.assertRaisesRegex(ValueError, "CDP_PROCESS_READ_FAILED"):
                CdpProcessDomReader(**CONFIG)()

    def test_configuration_rejected_before_start(self):
        for changes in ({"target_id": "other"}, {"selector": ""}, {"timeout_seconds": True}, {"timeout_seconds": 61}):
            config = {**CONFIG, **changes}
            with patch("consilium.adapters.cdp_process_reader.BoundedReadProcess") as process, self.assertRaisesRegex(ValueError, "CDP_PROCESS_CONFIGURATION_INVALID"):
                CdpProcessDomReader(**config)
            process.assert_not_called()

    def test_cli_argument_boundary_has_no_stdout(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(main([]), 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "CDP_DOM_READ_REQUIRES_CONFIG\n")

    def test_cli_malformed_input_private_no_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for raw in (b"private malformed", b'{"x":1,"x":2}', b'{"x":1e400}', b"[" * 65 + b"]" * 65,
                        json.dumps({**CONFIG, "extra": "private"}).encode(), b"x" * 16385):
                path.write_bytes(raw)
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), patch("consilium.shell.cdp_dom_read.connect_read_only") as connect:
                    self.assertEqual(main([str(path)]), 1)
                connect.assert_not_called()
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "CDP_DOM_READ_FAILED\n")
