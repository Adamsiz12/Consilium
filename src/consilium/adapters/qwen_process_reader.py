"""One bounded, owned observation process; commands never certify live origin."""

import base64
import binascii
import json

from consilium.adapters.qwen_page_reader import (
    MAX_CAPTURE_BYTES,
    _reject_constant,
    _require_bounded_depth,
    _unique_object,
    read_qwen_capture,
)
from consilium.adapters.qwen_site_reader import (
    QwenSiteRead,
    QwenSiteReceipt,
    verify_site_receipt,
)
from consilium.core.browser_probe import BrowserContext
from consilium.shell.bounded_read_process import BoundedReadProcess
from consilium.shell.qwen_capture_ingest import QwenCaptureRead

MAX_READER_BYTES = 3 * 1048576


def decode_reader_output(raw):
    invalid = False
    try:
        if type(raw) is not bytes or not raw or len(raw) > MAX_READER_BYTES:
            raise ValueError("size")
        _require_bounded_depth(raw)
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
        if (
            not isinstance(value, dict)
            or type(value.get("schema_version")) is not int
            or value["schema_version"] not in (1, 2)
        ):
            raise ValueError("schema")
        fields = {"schema_version", "before", "raw_capture_base64", "after"}
        if value["schema_version"] == 2:
            fields.add("site_receipt")
        if set(value) != fields or type(value["raw_capture_base64"]) is not str:
            raise ValueError("schema")
        capture = base64.b64decode(value["raw_capture_base64"], validate=True)
        if (
            not capture or len(capture) > MAX_CAPTURE_BYTES
            or base64.b64encode(capture).decode("ascii") != value["raw_capture_base64"]
        ):
            raise ValueError("capture")
        before = BrowserContext.model_validate_json(json.dumps(value["before"], allow_nan=False))
        after = BrowserContext.model_validate_json(json.dumps(value["after"], allow_nan=False))
        result = QwenCaptureRead(before, capture, after)
        if value["schema_version"] == 2:
            result = QwenSiteRead(result, QwenSiteReceipt.model_validate(value["site_receipt"]))
            verify_site_receipt(result)
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        invalid = True
    if invalid:
        raise ValueError("QWEN_READER_OUTPUT_INVALID")
    return result



def encode_reader_output(packet):
    """Build a private packet, preserving exact capture bytes; no live authority."""
    invalid = False
    try:
        observation = packet if type(packet) is QwenSiteRead else None
        if observation is not None:
            verify_site_receipt(observation)
            packet = observation.packet
        if type(packet) is not QwenCaptureRead:
            raise ValueError("packet")
        before = BrowserContext.model_validate(packet.before)
        after = BrowserContext.model_validate(packet.after)
        page = read_qwen_capture(packet.raw)
        identities = [
            (context.authentication, context.account_binding_id,
             context.conversation_binding_id, context.model_id)
            for context in (before, page.context, after)
        ]
        if identities[0][0] != "AUTHENTICATED" or len(set(identities)) != 1:
            raise ValueError("context")
        value = {
            "schema_version": 2 if observation is not None else 1,
            "before": before.model_dump(mode="json"),
            "raw_capture_base64": base64.b64encode(packet.raw).decode("ascii"),
            "after": after.model_dump(mode="json"),
        }
        if observation is not None:
            value["site_receipt"] = observation.receipt.model_dump(mode="json")
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        decode_reader_output(raw)
    except (ValueError, TypeError):
        invalid = True
    if invalid:
        raise ValueError("QWEN_READER_PACKET_INVALID")
    return raw

class QwenProcessReader(BoundedReadProcess):
    """One owned command; validates only the Qwen v1/v2 packet contract.

    The operator must authorize an observation-only command. This does not
    certify live origin or sandbox arbitrary command behavior. Existing error
    codes, byte bound, execution deadline and cleanup behavior are preserved.
    """

    ERROR_PREFIX = "QWEN_READER"

    def __call__(self):
        return decode_reader_output(self.run(max_bytes=MAX_READER_BYTES))
