"""Shared observation process byte bounds, with actual local commands."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from consilium.shell.bounded_read_process import BoundedReadProcess

FIXTURE = Path(__file__).with_name("qwen_reader_fixture.py")


class BoundedReadProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private.bin"
        self.path.write_bytes(b"\xff\x00\r\nprivate")

    def command(self, mode="success"):
        return (sys.executable, str(FIXTURE), mode, str(self.path))

    def test_actual_bytes_preserved_without_protocol_interpretation(self):
        self.assertEqual(BoundedReadProcess(self.command()).run(), self.path.read_bytes())

    def test_actual_custom_output_limit_enforced(self):
        with self.assertRaisesRegex(ValueError, "^BOUNDED_READER_OUTPUT_OVERSIZED$"):
            BoundedReadProcess(self.command()).run(max_bytes=2)
        self.assertEqual(self.path.read_bytes(), b"\xff\x00\r\nprivate")

    def test_actual_child_failure_discards_private_stderr(self):
        with self.assertRaisesRegex(ValueError, "^BOUNDED_READER_PROCESS_FAILED$") as caught:
            BoundedReadProcess(self.command("failure")).run()
        self.assertIsNone(caught.exception.__context__)

    def test_invalid_output_budget_prevents_spawn(self):
        for limit in (True, 0, -1, 3 * 1048576 + 1, 1.0):
            with patch("consilium.shell.bounded_read_process.subprocess.Popen") as popen, self.assertRaisesRegex(ValueError, "BOUNDED_READER_CONFIGURATION_INVALID"):
                BoundedReadProcess(self.command()).run(max_bytes=limit)
            popen.assert_not_called()

    def test_spawn_error_has_no_private_exception_context(self):
        with patch("consilium.shell.bounded_read_process.subprocess.Popen", side_effect=OSError("private command")), self.assertRaisesRegex(ValueError, "^BOUNDED_READER_START_FAILED$") as caught:
            BoundedReadProcess(self.command()).run()
        self.assertIsNone(caught.exception.__context__)

    def test_command_configuration_exact_types(self):
        for command in ([], (), ("",), (b"bytes",), ("bad\x00arg",)):
            with self.assertRaisesRegex(ValueError, "BOUNDED_READER_CONFIGURATION_INVALID"):
                BoundedReadProcess(command)
