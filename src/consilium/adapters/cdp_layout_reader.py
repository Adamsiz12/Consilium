"""Read selected Chromium layout text without evaluating page JavaScript."""

import json
import math
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from consilium.adapters.cdp_dom_wire import _digest
from consilium.adapters.cdp_read_only import CdpDomReader, _command
from consilium.adapters.qwen_page_reader import _require_bounded_depth, _unique_object
from consilium.adapters.qwen_site_reader import _valid_surface_id, _valid_url

STYLES = ["display", "visibility", "opacity", "content-visibility"]
MAX_NODES = 20000
MAX_TEXT_BYTES = 1048576
SCOPE = "LAYOUT_TEXT_NOT_VIEWPORT_OR_LIVE_RESPONSE_CERTIFICATION"


def valid_layout_url(value):
    if _valid_url(value):
        return True
    if type(value) is not str or len(value) > 8192 or any(ord(c) <= 32 or ord(c) >= 127 or c == "\\" for c in value):
        return False
    p = urlsplit(value)
    return (p.scheme == "http" and p.hostname == "127.0.0.1" and p.port is not None
            and 1 <= p.port <= 65535 and p.netloc == "127.0.0.1:" + str(p.port)
            and not p.query and not p.fragment and "?" not in value and "#" not in value)


@dataclass(frozen=True)
class CdpLayoutObservation:
    url: str
    target_id: str
    frame_id: str
    loader_id: str
    backend_node_id: int
    text: str
    scope: str = SCOPE


def selected_layout_text(snapshot, *, backend_node_id, frame_id, expected_url):
    """Conservatively exclude hidden/transparent layout and foreign subtrees.

    Layout evidence is not pixel visibility: offscreen and occluded text may be
    included. Shadow roots, iframe documents, inaccessible/oversized graphs and
    unrecognized styles cannot establish a full provider conversation history.
    """
    strings, documents = snapshot["strings"], snapshot["documents"]
    if type(strings) is not list or type(documents) is not list or not 1 <= len(documents) <= 64:
        raise ValueError("snapshot")

    def string(index):
        if type(index) is not int or not 0 <= index < len(strings) or type(strings[index]) is not str:
            raise ValueError("string")
        return strings[index]

    matching = [d for d in documents if string(d["frameId"]) == frame_id]
    if len(matching) != 1 or string(matching[0]["documentURL"]) != expected_url:
        raise ValueError("frame")
    nodes, layout = matching[0]["nodes"], matching[0]["layout"]
    parents, backend = nodes["parentIndex"], nodes["backendNodeId"]
    if (type(parents) is not list or type(backend) is not list
            or not 1 <= len(parents) <= MAX_NODES or len(backend) != len(parents)
            or any(type(x) is not int or x <= 0 for x in backend)
            or len(set(backend)) != len(backend)
            or type(backend_node_id) is not int or backend_node_id <= 0
            or backend.count(backend_node_id) != 1):
        raise ValueError("nodes")
    chosen = backend.index(backend_node_id)
    descendants, depths = [], []
    for index, parent in enumerate(parents):
        if type(parent) is not int or not -1 <= parent < index or index > 0 and parent < 0:
            raise ValueError("parent")
        depth = 0 if parent < 0 else depths[parent] + 1
        if depth > 256:
            raise ValueError("depth")
        depths.append(depth)
        descendants.append(index == chosen or parent >= 0 and descendants[parent])
    indices, texts, styles, bounds = (layout[k] for k in ("nodeIndex", "text", "styles", "bounds"))
    if (any(type(x) is not list for x in (indices, texts, styles, bounds))
            or len(indices) > MAX_NODES or any(len(x) != len(indices) for x in (texts, styles, bounds))
            or any(type(i) is not int or not 0 <= i < len(parents) for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError("layout")
    hidden = set()
    for node, style, rect, text in zip(indices, styles, bounds, texts):
        if (node == 0 and parents[node] == -1 and style == []
                and type(text) is int and text == -1):
            # Chromium's document layout root has no computed CSS or text.
            continue
        if type(style) is not list or len(style) != 4 or type(rect) is not list or len(rect) != 4:
            raise ValueError("style")
        display, visibility, opacity, content = map(string, style)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in rect):
            raise ValueError("bounds")
        alpha = float(opacity)
        if not math.isfinite(alpha) or not 0 <= alpha <= 1 or rect[2] < 0 or rect[3] < 0:
            raise ValueError("opacity")
        if (display == "none" or visibility != "visible" or alpha == 0
                or content == "hidden" or rect[2] == 0 or rect[3] == 0):
            hidden.add(node)
    rejected = []
    for index, parent in enumerate(parents):
        rejected.append(index in hidden or parent >= 0 and rejected[parent])
    parts, size = [], 0
    for node, text in zip(indices, texts):
        # CDP uses -1 as the absent layout-text string sentinel.
        value = "" if type(text) is int and text == -1 else string(text)
        if descendants[node] and not rejected[node] and value:
            size += len(value.encode("utf-8")) + 1
            if size > MAX_TEXT_BYTES:
                raise ValueError("text size")
            parts.append(value)
    return "\n".join(parts)


class CdpLayoutReader(CdpDomReader):
    """Exactly one selected subtree, bound to unchanged target/frame/loader."""

    URL_VALIDATOR = staticmethod(valid_layout_url)

    def __call__(self):
        failed = False
        try:
            before = self._surface()
            root = self.session.read("DOM.getDocument", depth=0, pierce=False)["root"]["nodeId"]
            nodes = self.session.read("DOM.querySelectorAll", nodeId=root, selector=self.selector)["nodeIds"]
            if type(nodes) is not list or len(nodes) != 1:
                raise ValueError("ambiguous")
            backend = self.session.read("DOM.describeNode", nodeId=nodes[0], depth=0, pierce=False)["node"]["backendNodeId"]
            snapshot = self.session.read("DOMSnapshot.captureSnapshot", computedStyles=list(STYLES),
                                         includeDOMRects=True, includePaintOrder=False)
            text = selected_layout_text(snapshot, backend_node_id=backend,
                                        frame_id=before[0], expected_url=self.expected_url)
            if self._surface() != before:
                raise ValueError("navigation")
            observation = CdpLayoutObservation(self.expected_url, self.target_id, *before, backend, text)
        except Exception:  # noqa: BLE001 -- page and protocol details are private
            failed = True
        if failed:
            self.session.close()
            raise ValueError("CDP_LAYOUT_READ_FAILED")
        return observation


def decode_layout_output(raw, *, selector):
    failed = False
    try:
        if not _command("DOM.querySelectorAll", {"nodeId": 1, "selector": selector}):
            raise ValueError("selector")
        if type(raw) is not bytes or not raw or len(raw) > 2 * 1048576:
            raise ValueError("size")
        _require_bounded_depth(raw)
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=lambda _: None)
        if (type(value) is not dict or set(value) != {"kind", "selector_sha256", "observation", "text_sha256"}
                or value["kind"] != "CDP_LAYOUT_TEXT_V1" or value["selector_sha256"] != _digest(selector)):
            raise ValueError("schema")
        observation = CdpLayoutObservation(**value["observation"])
        if (not valid_layout_url(observation.url) or observation.scope != SCOPE
                or not all(_valid_surface_id(v) for v in (observation.target_id, observation.frame_id, observation.loader_id))
                or type(observation.backend_node_id) is not int or observation.backend_node_id <= 0
                or type(observation.text) is not str or len(observation.text.encode()) > MAX_TEXT_BYTES
                or value["text_sha256"] != _digest(observation.text)):
            raise ValueError("observation")
    except Exception:  # noqa: BLE001 -- private wire data
        failed = True
    if failed:
        raise ValueError("CDP_LAYOUT_OUTPUT_INVALID")
    return observation


def encode_layout_output(observation, *, selector):
    value = {"kind": "CDP_LAYOUT_TEXT_V1", "selector_sha256": _digest(selector),
             "observation": asdict(observation), "text_sha256": _digest(observation.text)}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    decode_layout_output(raw, selector=selector)
    return raw
