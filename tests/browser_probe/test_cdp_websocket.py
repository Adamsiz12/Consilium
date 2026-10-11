"""Optional transport dependency and privacy gates without importing a browser."""

import types
import unittest
from importlib.metadata import PackageNotFoundError
from unittest.mock import Mock, patch

from consilium.adapters.cdp_read_only import MAX_MESSAGE_BYTES
from consilium.adapters.cdp_websocket import connect_read_only

ENDPOINT = "ws://127.0.0.1:9222/devtools/page/tab-1"


class CdpWebSocketTests(unittest.TestCase):
    def setUp(self):
        self.connect = Mock(return_value=object())
        module = types.ModuleType("websockets.sync.client")
        module.connect = self.connect
        self.modules = {"websockets.sync.client": module}

    def test_pinned_read_only_transport_options(self):
        with patch("consilium.adapters.cdp_websocket.version", return_value="16.0"), patch.dict("sys.modules", self.modules):
            result = connect_read_only(ENDPOINT, 10)
        self.assertIs(result, self.connect.return_value)
        self.connect.assert_called_once_with(ENDPOINT, proxy=None, compression=None, open_timeout=10,
                                             close_timeout=1.0, max_size=MAX_MESSAGE_BYTES, max_queue=1,
                                             ping_interval=None, user_agent_header=None)

    def test_cleanup_timeout_never_exceeds_budget(self):
        with patch("consilium.adapters.cdp_websocket.version", return_value="16.0"), patch.dict("sys.modules", self.modules):
            connect_read_only(ENDPOINT, 0.25)
        self.assertEqual(self.connect.call_args.kwargs["close_timeout"], 0.25)

    def test_unavailable_dependency_has_private_error(self):
        with patch("consilium.adapters.cdp_websocket.version", side_effect=PackageNotFoundError("private path")), self.assertRaisesRegex(ValueError, "^CDP_TRANSPORT_UNAVAILABLE$") as caught:
            connect_read_only(ENDPOINT, 1)
        self.assertIsNone(caught.exception.__context__)

    def test_wrong_dependency_version_not_connected(self):
        with patch("consilium.adapters.cdp_websocket.version", return_value="17.1"), patch.dict("sys.modules", self.modules), self.assertRaisesRegex(ValueError, "CDP_TRANSPORT_UNAVAILABLE"):
            connect_read_only(ENDPOINT, 1)
        self.connect.assert_not_called()

    def test_remote_endpoint_rejected_before_dependency_loading(self):
        with patch("consilium.adapters.cdp_websocket.version") as version, self.assertRaisesRegex(ValueError, "CDP_TRANSPORT_UNAVAILABLE"):
            connect_read_only("ws://remote.test:9222/devtools/page/tab-1", 1)
        version.assert_not_called()

    def test_bad_timeout_rejected_before_dependency_loading(self):
        for timeout in (True, 0, 61, float("nan"), float("inf")):
            with patch("consilium.adapters.cdp_websocket.version") as version, self.assertRaisesRegex(ValueError, "CDP_TRANSPORT_UNAVAILABLE"):
                connect_read_only(ENDPOINT, timeout)
            version.assert_not_called()

    def test_handshake_failure_no_retry_and_private_error(self):
        self.connect.side_effect = RuntimeError("private handshake")
        with patch("consilium.adapters.cdp_websocket.version", return_value="16.0"), patch.dict("sys.modules", self.modules), self.assertRaisesRegex(ValueError, "^CDP_TRANSPORT_UNAVAILABLE$") as caught:
            connect_read_only(ENDPOINT, 1)
        self.assertIsNone(caught.exception.__context__)
        self.connect.assert_called_once()
