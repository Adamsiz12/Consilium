"""Explicit page-target CDP reads; injected transport, no browser discovery.

Transport connect/send/close must be bounded by the caller's owned process.
The receive loop has an absolute deadline, byte limits and an event limit.
This module does not assert rendered visibility or provider authenticity.
"""

import json
import math
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from consilium.adapters.qwen_page_reader import _require_bounded_depth, _unique_object
from consilium.adapters.qwen_site_reader import _valid_surface_id, _valid_url

MAX_MESSAGE_BYTES = 3 * 1048576
MAX_EVENTS = 64


def _endpoint(value):
    if type(value) is not str or len(value) > 1024 or any(
        ord(c) <= 32 or ord(c) >= 127 or c == "\\" for c in value
    ):
        return False
    p = urlsplit(value)
    return (p.scheme == "ws" and p.hostname in {"127.0.0.1", "::1"}
            and p.port is not None and 1 <= p.port <= 65535
            and p.username is None and p.password is None
            and not p.query and not p.fragment
            and p.path.startswith("/devtools/page/")
            and not any(c in value for c in "?#%")
            and re.fullmatch(r"[A-Za-z0-9_-]{1,256}", p.path.removeprefix("/devtools/page/")) is not None)


def _command(method, params):
    if type(params) is not dict:
        return False
    fields = {
        "Target.getTargetInfo": {"targetId"}, "Page.getFrameTree": set(),
        "DOM.getDocument": {"depth", "pierce"},
        "DOM.querySelectorAll": {"nodeId", "selector"},
        "DOM.getOuterHTML": {"nodeId"}, "DOM.getAttributes": {"nodeId"},
        "DOM.describeNode": {"nodeId", "depth", "pierce"},
        "DOMSnapshot.captureSnapshot": {"computedStyles", "includeDOMRects", "includePaintOrder"},
    }
    if method not in fields or set(params) != fields[method]:
        return False
    if method == "DOMSnapshot.captureSnapshot":
        return (type(params["computedStyles"]) is list
                and params["computedStyles"] == ["display", "visibility", "opacity", "content-visibility"]
                and params["includeDOMRects"] is True and params["includePaintOrder"] is False)
    if method == "Target.getTargetInfo":
        return type(params["targetId"]) is str and 0 < len(params["targetId"]) <= 256
    if method == "DOM.getDocument":
        return type(params["depth"]) is int and params["depth"] == 0 and params["pierce"] is False
    if "nodeId" in params and (type(params["nodeId"]) is not int or not 0 < params["nodeId"] <= 2**31 - 1):
        return False
    if method == "DOM.describeNode":
        return type(params["depth"]) is int and params["depth"] == 0 and params["pierce"] is False
    if "selector" in params:
        s = params["selector"]
        return type(s) is str and 0 < len(s) <= 1024 and not any(ord(c) < 32 for c in s)
    return True


def _constant(_value):
    raise ValueError("nonfinite")


class CdpReadOnlySession:
    """One explicit connection; rejected/failed reads poison it, with no retry.

    Factory receives endpoint and remaining seconds. Socket provides send(text),
    recv(timeout=seconds), close(). No arbitrary CDP method can be dispatched.
    Timeout does not sandbox injected transport; use the owned worker for that.
    """

    def __init__(self, endpoint, factory, *, timeout=10.0, clock=time.monotonic):
        invalid = False
        try:
            invalid = (not _endpoint(endpoint) or not callable(factory)
                       or type(timeout) not in (int, float) or not math.isfinite(timeout)
                       or not 0 < timeout <= 60 or not callable(clock))
        except Exception:  # noqa: BLE001 -- sanitize configuration
            invalid = True
        if invalid:
            raise ValueError("CDP_CONFIGURATION_INVALID")
        self.endpoint, self.factory, self.clock = endpoint, factory, clock
        self.deadline = clock() + timeout
        self.socket = None
        self.sequence = 0
        self.closed = False
        self._read_lock = threading.Lock()

    def _remaining(self):
        value = self.deadline - self.clock()
        if value <= 0:
            raise TimeoutError("deadline")
        return value

    def close(self):
        socket, self.socket = self.socket, None
        self.closed = True
        if socket is not None:
            try:
                socket.close()
            except Exception:  # noqa: BLE001, S110 -- best effort, never expose transport details
                pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def read(self, method, **params):
        if not self._read_lock.acquire(blocking=False):
            raise ValueError("CDP_READ_BUSY")
        try:
            return self._read_once(method, params)
        finally:
            self._read_lock.release()

    def _read_once(self, method, params):
        failed = False
        try:
            if self.closed or not _command(method, params):
                raise ValueError("command")
            if method == "Target.getTargetInfo" and params["targetId"] != urlsplit(self.endpoint).path.rsplit("/", 1)[1]:
                raise ValueError("target binding")
            self._remaining()
            if self.socket is None:
                self.socket = self.factory(self.endpoint, self._remaining())
            self._remaining()
            self.sequence += 1
            self.socket.send(json.dumps({"id": self.sequence, "method": method, "params": params},
                                        allow_nan=False, separators=(",", ":")))
            for _ in range(MAX_EVENTS + 1):
                raw = self.socket.recv(timeout=self._remaining())
                self._remaining()
                if type(raw) is not str or not raw or len(raw) > MAX_MESSAGE_BYTES:
                    raise ValueError("frame")
                data = raw.encode("utf-8")
                if len(data) > MAX_MESSAGE_BYTES:
                    raise ValueError("bytes")
                _require_bounded_depth(data)
                message = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_constant)
                json.dumps(message, allow_nan=False)
                if type(message) is not dict or "sessionId" in message:
                    raise ValueError("envelope")
                if "id" not in message:
                    if set(message) - {"method", "params"} or type(message.get("method")) is not str or not message["method"]:
                        raise ValueError("event")
                    if "params" in message and type(message["params"]) is not dict:
                        raise ValueError("event")
                    if message["method"] in {"DOM.documentUpdated", "Page.frameNavigated",
                                             "Inspector.detached", "Target.detachedFromTarget"}:
                        raise ValueError("surface changed")
                    continue
                if (type(message["id"]) is not int or message["id"] != self.sequence
                        or set(message) != {"id", "result"} or type(message["result"]) is not dict):
                    raise ValueError("reply")
                return message["result"]
            raise ValueError("event limit")
        except Exception:  # noqa: BLE001 -- protocol failures may contain private page data
            failed = True
        if failed:
            self.close()
            raise ValueError("CDP_READ_FAILED")


@dataclass(frozen=True)
class CdpDomObservation:
    """Raw DOM evidence, never automatically classified as visible/completed."""

    url: str
    target_id: str
    frame_id: str
    loader_id: str
    node_id: int
    outer_html: str


class CdpDomReader:
    """Read exactly one selected subtree, bracketed by target/frame checks."""

    URL_VALIDATOR = staticmethod(_valid_url)

    def __init__(self, session, *, target_id, expected_url, selector):
        invalid = False
        try:
            invalid = (type(session) is not CdpReadOnlySession or not self.URL_VALIDATOR(expected_url)
                       or not _command("Target.getTargetInfo", {"targetId": target_id})
                       or urlsplit(session.endpoint).path != "/devtools/page/" + target_id
                       or not _command("DOM.querySelectorAll", {"nodeId": 1, "selector": selector}))
        except Exception:  # noqa: BLE001 -- private configuration
            invalid = True
        if invalid:
            raise ValueError("CDP_DOM_CONFIGURATION_INVALID")
        self.session = session
        self.target_id, self.expected_url, self.selector = target_id, expected_url, selector

    def _surface(self):
        target = self.session.read("Target.getTargetInfo", targetId=self.target_id)["targetInfo"]
        frame = self.session.read("Page.getFrameTree")["frameTree"]["frame"]
        if (target["targetId"] != self.target_id or target["type"] != "page"
                or target["url"] != self.expected_url or frame["url"] != self.expected_url):
            raise ValueError("target")
        for field in ("id", "loaderId"):
            if not _valid_surface_id(frame[field]):
                raise ValueError("frame")
        return frame["id"], frame["loaderId"]

    def __call__(self):
        failed = False
        try:
            before = self._surface()
            root = self.session.read("DOM.getDocument", depth=0, pierce=False)["root"]["nodeId"]
            nodes = self.session.read("DOM.querySelectorAll", nodeId=root, selector=self.selector)["nodeIds"]
            if type(nodes) is not list or len(nodes) != 1 or type(nodes[0]) is not int or not 0 < nodes[0] <= 2**31 - 1:
                raise ValueError("ambiguous subtree")
            html = self.session.read("DOM.getOuterHTML", nodeId=nodes[0])["outerHTML"]
            if type(html) is not str or not html:
                raise ValueError("html")
            if self._surface() != before:
                raise ValueError("navigation")
            return CdpDomObservation(self.expected_url, self.target_id, *before, nodes[0], html)
        except Exception:  # noqa: BLE001 -- private DOM errors
            failed = True
        if failed:
            self.session.close()
            raise ValueError("CDP_DOM_READ_FAILED")
