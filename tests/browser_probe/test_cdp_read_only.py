"""Protocol fixtures exercise reads, not a live browser or Qwen profile."""

import json
import unittest
from unittest.mock import patch

from consilium.adapters.cdp_read_only import CdpDomReader, CdpReadOnlySession

ENDPOINT = "ws://127.0.0.1:9222/devtools/page/tab-1"
URL = "https://example.test/conversation/fixture"


class Socket:
    def __init__(self, transform=None):
        self.calls, self.closed, self.pending = [], 0, []
        self.transform = transform

    def send(self, raw):
        request = json.loads(raw)
        self.calls.append(request)
        method = request["method"]
        result = {
            "Target.getTargetInfo": {"targetInfo": {"targetId": "tab-1", "type": "page", "url": URL}},
            "Page.getFrameTree": {"frameTree": {"frame": {"id": "frame-1", "loaderId": "doc-1", "url": URL}}},
            "DOM.getDocument": {"root": {"nodeId": 1}},
            "DOM.querySelectorAll": {"nodeIds": [2]},
            "DOM.getOuterHTML": {"outerHTML": "<div>private answer</div>"},
            "DOM.getAttributes": {"attributes": ["id", "answer"]},
        }[method]
        reply = {"id": request["id"], "result": result}
        if self.transform:
            reply = self.transform(request, reply)
        self.pending.append(json.dumps(reply) if type(reply) is dict else reply)

    def recv(self, *, timeout):
        assert timeout > 0
        return self.pending.pop(0)

    def close(self):
        self.closed += 1


class CdpReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.socket = Socket()
        self.opens = []
        self.now = 0.0
        self.session = self.make()
        self.addCleanup(self.session.close)

    def make(self):
        def factory(endpoint, timeout):
            self.opens.append((endpoint, timeout))
            return self.socket
        return CdpReadOnlySession(ENDPOINT, factory, clock=lambda: self.now)

    def reader(self, **changes):
        return CdpDomReader(self.session, **dict(target_id="tab-1", expected_url=URL,
                                                selector="#answer", **changes))

    def test_single_connection_exact_read_order_and_raw_html(self):
        result = self.reader()()
        self.assertEqual(result.outer_html, "<div>private answer</div>")
        self.assertEqual((result.target_id, result.frame_id, result.loader_id), ("tab-1", "frame-1", "doc-1"))
        self.assertEqual([r["method"] for r in self.socket.calls], [
            "Target.getTargetInfo", "Page.getFrameTree", "DOM.getDocument", "DOM.querySelectorAll",
            "DOM.getOuterHTML", "Target.getTargetInfo", "Page.getFrameTree"])
        self.assertEqual(len(self.opens), 1)

    def test_context_manager_closes_only_connection(self):
        with self.session:
            self.session.read("DOM.getAttributes", nodeId=1)
        self.assertEqual(self.socket.closed, 1)
        self.session.close()
        self.assertEqual(self.socket.closed, 1)

    def test_mutating_commands_fail_before_connect(self):
        for method in ("Runtime.evaluate", "Page.navigate", "Input.dispatchMouseEvent", "Browser.close",
                       "DOM.setAttributeValue", "Target.createTarget"):
            session = self.make()
            with self.assertRaisesRegex(ValueError, "^CDP_READ_FAILED$"):
                session.read(method)
        self.assertEqual(self.opens, [])

    def test_invalid_parameters_fail_before_connect(self):
        for method, params in (("DOM.getDocument", {"depth": -1, "pierce": True}),
                               ("DOM.getOuterHTML", {"nodeId": True}),
                               ("DOM.getOuterHTML", {"nodeId": 2**31}),
                               ("Page.getFrameTree", {"sessionId": "other"}),
                               ("DOM.querySelectorAll", {"nodeId": 1, "selector": "\n"})):
            with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
                self.make().read(method, **params)
        self.assertEqual(self.opens, [])

    def test_endpoint_rejects_remote_browser_credentials_and_encoded_path(self):
        for endpoint in ("ws://localhost:9222/devtools/page/tab-1", "ws://remote.test:9222/devtools/page/tab-1",
                         "ws://127.0.0.1:9222/devtools/browser/tab-1", ENDPOINT + "?secret=value",
                         ENDPOINT + "/child", ENDPOINT + "?", ENDPOINT + "#",
                         ENDPOINT.replace("tab-1", "%74ab-1"), "ws://user@127.0.0.1:9222/devtools/page/tab-1",
                         "ws://127.0.0.1:99999/devtools/page/tab-1", "wss://127.0.0.1:9222/devtools/page/tab-1"):
            with self.assertRaisesRegex(ValueError, "^CDP_CONFIGURATION_INVALID$") as caught:
                CdpReadOnlySession(endpoint, lambda *_: None)
            self.assertIsNone(caught.exception.__context__)

    def test_timeout_configuration_exact_and_finite(self):
        for timeout in (True, 0, -1, 61, float("nan"), float("inf"), "1"):
            with self.assertRaisesRegex(ValueError, "CDP_CONFIGURATION_INVALID"):
                CdpReadOnlySession(ENDPOINT, lambda *_: None, timeout=timeout)

    def test_expired_session_never_connects(self):
        self.now = 11
        with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            self.session.read("Page.getFrameTree")
        self.assertEqual(self.opens, [])

    def test_reply_after_deadline_rejected(self):
        def transform(_request, reply):
            self.now = 11
            return reply
        self.socket.transform = transform
        with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            self.session.read("Page.getFrameTree")
        self.assertEqual(self.socket.closed, 1)

    def test_transport_failure_private_and_no_retry(self):
        with patch.object(self.socket, "recv", side_effect=RuntimeError("private token")), self.assertRaisesRegex(ValueError, "^CDP_READ_FAILED$") as caught:
            self.session.read("Page.getFrameTree")
        self.assertIsNone(caught.exception.__context__)
        with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            self.session.read("Page.getFrameTree")
        self.assertEqual(len(self.opens), 1)
        self.assertEqual(len(self.socket.calls), 1)

    def test_malformed_replies_reject_without_private_content(self):
        for raw in ('{"id":1,"id":1,"result":{}}', '{"id":true,"result":{}}',
                    '{"id":2,"result":{}}', '{"id":1,"error":{"message":"secret"}}',
                    '{"id":1,"result":{},"sessionId":"other"}', '{"id":1,"result":[]}',
                    '{"id":1,"result":{"x":NaN}}', '{"id":1,"result":{"x":1e400}}',
                    '{"method":"event","params":[]}', '{"method":""}', b"binary", "", "[]"):
            self.socket = Socket(lambda *_args, raw=raw: raw)
            session = self.make()
            with self.assertRaisesRegex(ValueError, "^CDP_READ_FAILED$") as caught:
                session.read("Page.getFrameTree")
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(self.socket.closed, 1)

    def test_oversized_unicode_and_deep_frames_rejected(self):
        for raw in ("x" * (3 * 1048576 + 1), '"' + "ا" * (2 * 1048576) + '"', "[" * 65 + "]" * 65):
            self.socket = Socket(lambda *_args, raw=raw: raw)
            with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
                self.make().read("Page.getFrameTree")

    def test_unrelated_event_before_reply_is_allowed(self):
        self.socket.pending.append('{"method":"Page.lifecycleEvent","params":{}}')
        self.session.read("Page.getFrameTree")

    def test_navigation_and_detach_events_poison_session(self):
        for event in ("DOM.documentUpdated", "Page.frameNavigated", "Inspector.detached", "Target.detachedFromTarget"):
            self.socket = Socket()
            self.socket.pending.append(json.dumps({"method": event}))
            with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
                self.make().read("Page.getFrameTree")

    def test_event_flood_is_bounded(self):
        self.socket.pending = ['{"method":"Event"}'] * 65
        with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            self.session.read("Page.getFrameTree")
        self.assertEqual(len(self.socket.pending), 1)

    def test_dom_wrong_target_type_or_url_rejected_before_subtree(self):
        for field, value in (("targetId", "other"), ("type", "worker"), ("url", "https://other.test/")):
            def transform(request, reply, field=field, value=value):
                if request["method"] == "Target.getTargetInfo":
                    reply["result"]["targetInfo"][field] = value
                return reply
            self.socket = Socket(transform)
            self.session = self.make()
            with self.assertRaisesRegex(ValueError, "CDP_DOM_READ_FAILED"):
                self.reader()()
            self.assertEqual(len(self.socket.calls), 2)

    def test_dom_missing_or_ambiguous_subtree_rejected(self):
        for nodes in ([], [2, 3], [True], [0], [2**31], "2"):
            def transform(request, reply, nodes=nodes):
                if request["method"] == "DOM.querySelectorAll":
                    reply["result"]["nodeIds"] = nodes
                return reply
            self.socket = Socket(transform)
            self.session = self.make()
            with self.assertRaisesRegex(ValueError, "CDP_DOM_READ_FAILED"):
                self.reader()()
            self.assertNotIn("DOM.getOuterHTML", [x["method"] for x in self.socket.calls])

    def test_dom_loader_or_frame_drift_rejected(self):
        for field in ("id", "loaderId", "url"):
            def transform(request, reply, field=field):
                if request["method"] == "Page.getFrameTree" and request["id"] > 2:
                    reply["result"]["frameTree"]["frame"][field] = "changed"
                return reply
            self.socket = Socket(transform)
            self.session = self.make()
            with self.assertRaisesRegex(ValueError, "CDP_DOM_READ_FAILED"):
                self.reader()()
            self.assertEqual(self.socket.closed, 1)

    def test_dom_configuration_binds_endpoint_and_validates_without_read(self):
        for changes in ({"target_id": "other"}, {"selector": ""}, {"expected_url": "http://example.test/"}):
            config = {"target_id": "tab-1", "expected_url": URL, "selector": "#answer"}
            config.update(changes)
            with self.assertRaisesRegex(ValueError, "CDP_DOM_CONFIGURATION_INVALID"):
                CdpDomReader(self.session, **config)
        self.assertEqual(self.opens, [])

    def test_dom_malformed_html_private_error(self):
        self.socket.transform = lambda req, reply: (
            {"id": req["id"], "result": {"outerHTML": None}}
            if req["method"] == "DOM.getOuterHTML" else reply)
        with self.assertRaisesRegex(ValueError, "CDP_DOM_READ_FAILED") as caught:
            self.reader()()
        self.assertIsNone(caught.exception.__context__)

    def test_ipv6_loopback_configuration(self):
        session = CdpReadOnlySession("ws://[::1]:9222/devtools/page/tab-1", lambda *_: self.socket)
        session.read("Page.getFrameTree")
        session.close()

    def test_connect_returning_after_deadline_never_sends(self):
        def factory(*_args):
            self.now = 11
            return self.socket
        session = CdpReadOnlySession(ENDPOINT, factory, clock=lambda: self.now)
        with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            session.read("Page.getFrameTree")
        self.assertEqual(self.socket.calls, [])
        self.assertEqual(self.socket.closed, 1)

    def test_other_target_metadata_rejected_before_connect(self):
        with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
            self.session.read("Target.getTargetInfo", targetId="other")
        self.assertEqual(self.opens, [])

    def test_concurrent_read_rejected_without_disturbing_active_read(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        original = self.socket.recv
        values, errors = [], []
        def recv(**kwargs):
            entered.set()
            if not release.wait(2):
                raise TimeoutError("test rendezvous")
            return original(**kwargs)
        def first():
            try:
                values.append(self.session.read("Page.getFrameTree"))
            except Exception as exc:  # noqa: BLE001 -- record fixture outcome
                errors.append(type(exc).__name__)
        self.socket.recv = recv
        thread = threading.Thread(target=first)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError, "^CDP_READ_BUSY$"):
                self.session.read("DOM.getAttributes", nodeId=2)
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(values), 1)
        self.assertEqual(len(self.socket.calls), 1)
        self.assertEqual(self.socket.closed, 0)

    def test_invalid_frame_identity_rejected_before_dom_query(self):
        for value in (None, "", " ", "doc\nsecret", "x" * 257):
            def transform(request, reply, value=value):
                if request["method"] == "Page.getFrameTree":
                    reply["result"]["frameTree"]["frame"]["loaderId"] = value
                return reply
            self.socket = Socket(transform)
            self.session = self.make()
            with self.assertRaisesRegex(ValueError, "CDP_DOM_READ_FAILED"):
                self.reader()()
            self.assertEqual(len(self.socket.calls), 2)
