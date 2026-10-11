#!/usr/bin/env python3
"""Real loopback WebSocket exchange with a CDP fixture, never a browser proof."""

import json
import platform
import sys
import threading
import unittest
from importlib.metadata import version
from pathlib import Path

import qualityctl as q

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests/browser_probe")]
from test_cdp_read_only import URL, Socket
from websockets.sync.server import serve

from consilium.adapters.cdp_process_reader import CdpProcessDomReader
from consilium.adapters.cdp_read_only import (
    CdpDomReader,
    CdpReadOnlySession,
)
from consilium.adapters.cdp_websocket import connect_read_only


class LocalTransportProbe(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.server_errors = []
        self.event = None
        self.bad_reply = None
        self.silent = False
        self.release = threading.Event()
        self.server = serve(self.handle, "127.0.0.1", 0, compression=None,
                            ping_interval=None, close_timeout=1)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        port = self.server.socket.getsockname()[1]
        self.endpoint = f"ws://127.0.0.1:{port}/devtools/page/tab-1"

    def stop(self):
        self.release.set()
        self.server.shutdown()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.server_errors, [])

    def handle(self, connection):
        try:
            fixture = Socket()
            for raw in connection:
                request = json.loads(raw)
                self.commands.append(request["method"])
                if self.silent:
                    self.release.wait(2)
                    return
                fixture.send(raw)
                if self.event:
                    connection.send(json.dumps({"method": self.event}))
                connection.send(self.bad_reply or fixture.recv(timeout=1))
        except Exception as exc:  # noqa: BLE001 -- only fixed fixture exchanges
            from websockets.exceptions import ConnectionClosed
            if not isinstance(exc, ConnectionClosed):
                self.server_errors.append(type(exc).__name__)

    def test_real_exchange_reads_exact_target_subtree(self):
        with CdpReadOnlySession(self.endpoint, connect_read_only) as session:
            result = CdpDomReader(session, target_id="tab-1", expected_url=URL, selector="#answer")()
            self.assertEqual(result.outer_html, "<div>private answer</div>")
        self.assertEqual(len(self.commands), 7)
        self.assertNotIn("Runtime.evaluate", self.commands)

    def test_actual_event_invalidates_read_without_retry(self):
        self.event = "DOM.documentUpdated"
        with CdpReadOnlySession(self.endpoint, connect_read_only) as session, self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            session.read("Page.getFrameTree")
        self.assertEqual(self.commands, ["Page.getFrameTree"])

    def test_actual_protocol_error_is_private(self):
        self.bad_reply = '{"id":1,"error":{"message":"private fixture secret"}}'
        with CdpReadOnlySession(self.endpoint, connect_read_only) as session, self.assertRaisesRegex(ValueError, "^CDP_READ_FAILED$") as caught:
            session.read("Page.getFrameTree")
        self.assertIsNone(caught.exception.__context__)

    def test_silent_connection_obeys_receive_deadline(self):
        self.silent = True
        with CdpReadOnlySession(self.endpoint, connect_read_only, timeout=0.05) as session, self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            session.read("Page.getFrameTree")
        self.assertEqual(self.commands, ["Page.getFrameTree"])

    def test_actual_owned_process_reads_selected_subtree(self):
        reader = CdpProcessDomReader(endpoint=self.endpoint, target_id="tab-1", expected_url=URL,
                                     selector="#answer", timeout_seconds=10)
        self.assertEqual(reader().outer_html, "<div>private answer</div>")
        self.assertEqual(len(self.commands), 7)

    def test_actual_owned_process_protocol_failure_is_private(self):
        self.bad_reply = '{"id":1,"error":{"message":"private"}}'
        reader = CdpProcessDomReader(endpoint=self.endpoint, target_id="tab-1", expected_url=URL,
                                     selector="#answer", timeout_seconds=10)
        with self.assertRaisesRegex(ValueError, "^CDP_PROCESS_READ_FAILED$"):
            reader()
        self.assertEqual(self.commands, ["Target.getTargetInfo"])

    def test_actual_owned_process_silent_connection_terminates(self):
        self.silent = True
        reader = CdpProcessDomReader(endpoint=self.endpoint, target_id="tab-1", expected_url=URL,
                                     selector="#answer", timeout_seconds=1)
        with self.assertRaisesRegex(ValueError, "^CDP_PROCESS_READ_FAILED$"):
            reader()
        self.assertEqual(self.commands, ["Target.getTargetInfo"])

    def test_proxy_environment_not_used(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"HTTP_PROXY": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1"}), CdpReadOnlySession(self.endpoint, connect_read_only) as session:
            session.read("Page.getFrameTree")
        self.assertEqual(self.commands, ["Page.getFrameTree"])


def main():
    before = q.source_digest(ROOT)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LocalTransportProbe)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = q.source_digest(ROOT)
    report = {
        "scope": "REAL_LOOPBACK_WEBSOCKET_CDP_FIXTURE_NOT_LIVE_BROWSER",
        "status": "PASS" if result.wasSuccessful() and before == after else "FAIL",
        "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "source_digest_before": before, "source_digest_after": after,
        "host": {"system": platform.system(), "python": platform.python_version(),
                 "websockets": version("websockets")},
        "browser_connected": False, "provider_calls": 0, "phase_accepted": False,
    }
    folder = ROOT / "evidence/cdp-transport-probe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "RUN.json").write_bytes(q.encoded(report))
    print(json.dumps(report))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
