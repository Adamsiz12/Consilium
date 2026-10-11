"""Private recorded-file producer for receipt wire v2; never a live site driver."""

import hashlib
import json
import sys
from typing import Literal

from pydantic import field_validator

from consilium.adapters.qwen_page_reader import (
    MAX_CAPTURE_BYTES,
    _reject_constant,
    _require_bounded_depth,
    _unique_object,
)
from consilium.adapters.qwen_process_reader import encode_reader_output
from consilium.adapters.qwen_site_reader import (
    QwenSiteRead,
    QwenSiteReceipt,
    verify_site_receipt,
)
from consilium.core.browser_probe import BrowserContext
from consilium.core.contracts import Contract, Sha256
from consilium.shell.qwen_capture_ingest import QwenCaptureRead
from consilium.shell.qwen_saved_read import MAX_CONTEXT_BYTES, bounded_file

MAX_RECEIPT_BYTES = 4096
MAX_MANIFEST_BYTES = 4096


class QwenRecordedManifest(Contract):
    """Expected hashes supplied by the operator, not authenticated provenance."""

    schema_version: Literal[1]
    before_sha256: Sha256
    capture_sha256: Sha256
    after_sha256: Sha256
    receipt_sha256: Sha256

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("version")
        return value


def _json(raw):
    _require_bounded_depth(raw)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


def read_saved_site(before_path, capture_path, after_path, receipt_path, manifest_path):
    """Read a declared snapshot with pinned role hashes and a stable manifest.

    Files are observations already recorded elsewhere; no browser is read here.
    The manifest is read twice to reject changes during assembly. This does not
    certify freshness, signer identity, or the truth of any recorded context.
    """
    invalid = False
    try:
        manifest_raw = bounded_file(manifest_path, MAX_MANIFEST_BYTES)
        manifest = QwenRecordedManifest.model_validate(_json(manifest_raw))
        before_raw = bounded_file(before_path, MAX_CONTEXT_BYTES)
        capture_raw = bounded_file(capture_path, MAX_CAPTURE_BYTES)
        after_raw = bounded_file(after_path, MAX_CONTEXT_BYTES)
        receipt_raw = bounded_file(receipt_path, MAX_RECEIPT_BYTES)
        for raw, expected in (
            (before_raw, manifest.before_sha256), (capture_raw, manifest.capture_sha256),
            (after_raw, manifest.after_sha256), (receipt_raw, manifest.receipt_sha256),
        ):
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("hash")
        before = BrowserContext.model_validate_json(json.dumps(_json(before_raw), allow_nan=False))
        after = BrowserContext.model_validate_json(json.dumps(_json(after_raw), allow_nan=False))
        observation = QwenSiteRead(
            QwenCaptureRead(before, capture_raw, after),
            QwenSiteReceipt.model_validate(_json(receipt_raw)),
        )
        verify_site_receipt(observation)
        if bounded_file(manifest_path, MAX_MANIFEST_BYTES) != manifest_raw:
            raise ValueError("manifest changed")
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        invalid = True
    if invalid:
        raise ValueError("QWEN_SAVED_SITE_INVALID")
    return observation


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 5:
        print("QWEN_SAVED_SITE_REQUIRES_FIVE_FILES", file=sys.stderr)
        return 2
    invalid = False
    try:
        result = encode_reader_output(read_saved_site(*argv))
    except (OSError, ValueError, TypeError, UnicodeError):
        invalid = True
    if invalid:
        print("QWEN_SAVED_SITE_INVALID", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
