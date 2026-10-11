"""Private raw DOM envelope, incompatible with the Qwen response contract."""

import hashlib
import json
from dataclasses import asdict

from consilium.adapters.cdp_read_only import (
    MAX_MESSAGE_BYTES,
    CdpDomObservation,
    _command,
)
from consilium.adapters.qwen_page_reader import _require_bounded_depth, _unique_object
from consilium.adapters.qwen_site_reader import _valid_surface_id, _valid_url

MAX_DOM_BYTES = 2 * 1048576
FIELDS = {"url", "target_id", "frame_id", "loader_id", "node_id", "outer_html"}


def _constant(_value):
    raise ValueError("nonfinite")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate(value):
    if type(value) is not dict or set(value) != FIELDS or not _valid_url(value["url"]):
        raise ValueError("fields")
    if not all(_valid_surface_id(value[key]) for key in ("target_id", "frame_id", "loader_id")):
        raise ValueError("identity")
    if type(value["node_id"]) is not int or not 0 < value["node_id"] <= 2**31 - 1:
        raise ValueError("node")
    html = value["outer_html"]
    if type(html) is not str or not html or len(html.encode("utf-8")) > MAX_DOM_BYTES:
        raise ValueError("html")
    return CdpDomObservation(**value)


def decode_dom_output(raw, *, selector):
    invalid = False
    try:
        if not _command("DOM.querySelectorAll", {"nodeId": 1, "selector": selector}):
            raise ValueError("selector")
        if type(raw) is not bytes or not raw or len(raw) > MAX_MESSAGE_BYTES:
            raise ValueError("size")
        _require_bounded_depth(raw)
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_constant)
        json.dumps(value, allow_nan=False)
        if (type(value) is not dict or set(value) != {"schema_version", "kind", "observation", "selector_sha256", "html_sha256"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["kind"] != "CDP_RAW_DOM_V1" or value["selector_sha256"] != _digest(selector)):
            raise ValueError("schema")
        result = _validate(value["observation"])
        if value["html_sha256"] != _digest(result.outer_html):
            raise ValueError("hash")
    except Exception:  # noqa: BLE001 -- raw DOM must remain private
        invalid = True
    if invalid:
        raise ValueError("CDP_DOM_OUTPUT_INVALID")
    return result


def encode_dom_output(observation, *, selector):
    invalid = False
    try:
        if type(observation) is not CdpDomObservation:
            raise ValueError("type")
        value = {"schema_version": 1, "kind": "CDP_RAW_DOM_V1", "observation": asdict(observation),
                 "selector_sha256": _digest(selector), "html_sha256": _digest(observation.outer_html)}
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        decode_dom_output(raw, selector=selector)
    except Exception:  # noqa: BLE001 -- raw DOM must remain private
        invalid = True
    if invalid:
        raise ValueError("CDP_DOM_PACKET_INVALID")
    return raw
