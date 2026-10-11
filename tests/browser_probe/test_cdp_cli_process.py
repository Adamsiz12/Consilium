"""Actual private CLI entry point rejection, without an endpoint connection."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CdpCliProcessTests(unittest.TestCase):
    def run_cli(self, *args):
        environment = dict(os.environ)
        package_root = str(Path(__file__).resolve().parents[2] / "src")
        environment["PYTHONPATH"] = package_root + (
            os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
        )
        return subprocess.run((sys.executable, "-m", "consilium.shell.cdp_dom_read", *args),
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=5, check=False, env=environment)

    def test_actual_argument_failure_empty_stdout_fixed_stderr(self):
        result = self.run_cli()
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (2, b"", b"CDP_DOM_READ_REQUIRES_CONFIG\n"))

    def test_actual_missing_config_error_private(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(str(Path(directory) / "private-missing.json"))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b"", b"CDP_DOM_READ_FAILED\n"))

    def test_actual_malformed_config_preserved_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            raw = b"private config secret"
            path.write_bytes(raw)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            result = self.run_cli(str(path))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b"", b"CDP_DOM_READ_FAILED\n"))

    def test_actual_remote_endpoint_rejected_without_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"endpoint": "ws://remote.invalid:9222/devtools/page/tab-1",
                                       "target_id": "tab-1", "expected_url": "https://example.test/page",
                                       "selector": "#answer", "timeout_seconds": 1}))
            result = self.run_cli(str(path))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b"", b"CDP_DOM_READ_FAILED\n"))
