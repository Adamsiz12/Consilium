"""Versioned declared acquisition receipts; integrity is not live authority."""

import json

from consilium.adapters.qwen_site_reader import (
    QwenSiteRead,
    QwenSiteReceipt,
    verify_site_receipt,
)
from consilium.core.browser_probe import BrowserContext
from consilium.shell.qwen_capture_ingest import QwenCaptureRead


def site_event(observation):
    receipt = verify_site_receipt(observation)
    return {
        "kind": "QWEN_SITE_PAGE",
        "reader_contract": "QWEN_SITE_RECEIPT_V1",
        "raw_capture_utf8": observation.packet.raw.decode("utf-8"),
        "before": observation.packet.before.model_dump(mode="json"),
        "after": observation.packet.after.model_dump(mode="json"),
        "site_receipt": receipt.model_dump(mode="json"),
    }


def site_read_from_event(value):
    invalid = False
    try:
        if (
            type(value) is not dict
            or set(value) != {"kind", "reader_contract", "raw_capture_utf8", "before", "after", "site_receipt"}
            or value["kind"] != "QWEN_SITE_PAGE"
            or value["reader_contract"] != "QWEN_SITE_RECEIPT_V1"
            or type(value["raw_capture_utf8"]) is not str
        ):
            raise ValueError("event")
        observation = QwenSiteRead(
            QwenCaptureRead(
                BrowserContext.model_validate_json(json.dumps(value["before"], allow_nan=False)),
                value["raw_capture_utf8"].encode("utf-8"),
                BrowserContext.model_validate_json(json.dumps(value["after"], allow_nan=False)),
            ),
            QwenSiteReceipt.model_validate(value["site_receipt"]),
        )
        verify_site_receipt(observation)
    except (ValueError, TypeError, UnicodeError):
        invalid = True
    if invalid:
        raise ValueError("JOURNAL_QWEN_SITE_EVENT_INVALID")
    return observation
