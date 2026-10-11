"""Gate an injected observation source; this is not a certified live driver."""

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from consilium.adapters.qwen_page_reader import read_qwen_capture
from consilium.core.browser_probe import BrowserContext
from consilium.core.contracts import Contract, Sha256
from consilium.shell.qwen_capture_ingest import QwenCaptureRead


@dataclass(frozen=True)
class QwenSurface:
    url: str
    tab_id: str
    document_id: str
    context: BrowserContext


@dataclass(frozen=True)
class QwenSurfaceCapture:
    surface: QwenSurface
    raw: bytes


class QwenSiteReceipt(Contract):
    """Hashes of declared observations; no live verification authority."""

    surface_sha256: Sha256
    capture_sha256: Sha256
    before_context_sha256: Sha256
    capture_context_sha256: Sha256
    after_context_sha256: Sha256


@dataclass(frozen=True)
class QwenSiteRead:
    packet: QwenCaptureRead
    receipt: QwenSiteReceipt


def _hash_value(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _context_hash(context):
    return _hash_value(BrowserContext.model_validate(context).model_dump(mode="json"))


def verify_site_receipt(observation):
    """Check packet correspondence, not the truth of source observations.

    Surface metadata is hashed for privacy and cannot be reconstructed here.
    Verifying that metadata against the actual browser is a separate step.
    """
    invalid = False
    try:
        if type(observation) is not QwenSiteRead or type(observation.packet) is not QwenCaptureRead:
            raise ValueError("observation")
        receipt = QwenSiteReceipt.model_validate(observation.receipt)
        packet = observation.packet
        page = read_qwen_capture(packet.raw)
        if (
            receipt.capture_sha256 != hashlib.sha256(packet.raw).hexdigest()
            or receipt.before_context_sha256 != _context_hash(packet.before)
            or receipt.capture_context_sha256 != _context_hash(page.context)
            or receipt.after_context_sha256 != _context_hash(packet.after)
            or packet.before.authentication != "AUTHENTICATED"
            or len({_identity(packet.before), _identity(page.context), _identity(packet.after)}) != 1
        ):
            raise ValueError("receipt")
    except Exception:  # noqa: BLE001 -- private packet validation must not escape
        invalid = True
    if invalid:
        raise ValueError("QWEN_SITE_RECEIPT_INVALID")
    return receipt


def _identity(context):
    return (context.authentication, context.account_binding_id,
            context.conversation_binding_id, context.model_id)


def _valid_url(value):
    if type(value) is not str or not value or len(value) > 8192 or any(
        ord(char) <= 32 or ord(char) >= 127 or char == "\\" for char in value
    ):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https" and bool(parsed.hostname)
        and parsed.username is None and parsed.password is None
        and parsed.port is None and not parsed.query and not parsed.fragment
        and parsed.netloc == parsed.hostname
    )


def _valid_surface_id(value):
    return (
        type(value) is str and 0 < len(value) <= 256 and bool(value.strip())
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


class QwenSiteReader:
    """Observe surface, capture, surface once, in that order, without retries.

    Source methods must be read-only and have their own bounded deadlines.
    They must observe context independently from response text. This wrapper
    does not sandbox the source or prove its claims. URL, tab and document
    gates are local checks, not durable or independently verified provenance.
    No provider origin is inferred: the operator supplies the exact URL.
    """

    def __init__(self, source, *, expected_url, expected_tab_id):
        invalid = False
        try:
            if (
                not _valid_url(expected_url)
                or not _valid_surface_id(expected_tab_id)
                or not callable(getattr(source, "read_surface", None))
                or not callable(getattr(source, "read_capture", None))
            ):
                invalid = True
        except Exception:  # noqa: BLE001 -- never export source/configuration details
            invalid = True
        if invalid:
            raise ValueError("QWEN_SITE_CONFIGURATION_INVALID")
        self.source = source
        self.expected_url = expected_url
        self.expected_tab_id = expected_tab_id

    def _surface(self, value):
        if (
            type(value) is not QwenSurface
            or type(value.url) is not str
            or not _valid_surface_id(value.tab_id)
            or value.url != self.expected_url or value.tab_id != self.expected_tab_id
            or not _valid_surface_id(value.document_id)
        ):
            raise ValueError("surface")
        context = BrowserContext.model_validate(value.context)
        if context.authentication != "AUTHENTICATED":
            raise ValueError("authentication")
        return context

    def __call__(self):
        return self.read_with_receipt().packet

    def read_with_receipt(self):
        """Return a packet and hash receipt from the same single acquisition.

        Receipt persistence and the process wire format are not provided here.
        This method never rereads the source to construct its receipt.
        """
        failed = False
        try:
            before = self.source.read_surface()
            first = self._surface(before)
            capture = self.source.read_capture()
            if type(capture) is not QwenSurfaceCapture:
                raise ValueError("capture")
            middle = self._surface(capture.surface)
            page = read_qwen_capture(capture.raw)
            if (
                capture.surface.document_id != before.document_id
                or _identity(first) != _identity(middle)
                or _identity(first) != _identity(page.context)
            ):
                raise ValueError("capture drift")
            after = self.source.read_surface()
            last = self._surface(after)
            if after.document_id != before.document_id or _identity(first) != _identity(last):
                raise ValueError("surface drift")
            packet = QwenCaptureRead(first, capture.raw, last)
            receipt = QwenSiteReceipt(
                surface_sha256=_hash_value({
                    "kind": "DECLARED_QWEN_SURFACE_V1", "url": before.url,
                    "tab_id": before.tab_id, "document_id": before.document_id,
                }),
                capture_sha256=hashlib.sha256(capture.raw).hexdigest(),
                before_context_sha256=_context_hash(first),
                capture_context_sha256=_context_hash(page.context),
                after_context_sha256=_context_hash(last),
            )
            result = QwenSiteRead(packet, receipt)
            verify_site_receipt(result)
        except Exception:  # noqa: BLE001 -- source exceptions can contain private page text
            failed = True
        if failed:
            raise ValueError("QWEN_SITE_READ_FAILED")
        return result
