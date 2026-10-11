"""Bounded HTTPS process transport, deliberately outside live council admission.

This is not a durable dispatch gate. Caller must first reserve the product
ledger's attempt and pass its actual context/provenance/free-budget gates.
A restarted instance is not evidence that an ambiguous attempt may be retried.
"""

import math
import sys
import tempfile
import threading
from pathlib import Path
from uuid import UUID

from consilium.adapters.api_http import (
    AccessBlocked,
    HttpGrant,
    HttpOutcome,
    credential_value,
    outcome_from_frames,
)
from consilium.adapters.api_process_progress import read_progress
from consilium.adapters.api_process_wire import (
    decode_process_outcome,
    encode_process_request,
)
from consilium.shell.bounded_read_process import BoundedCommandProcess


class ApiProcessTransport:
    """One packaged child per attempt, with no shell, HTTP redirect or retry.

    Credential is pinned in the child environment, never in argv or temp files.
    Max execution is 900 seconds plus at most five seconds of owned cleanup.
    A killed/malformed child cannot prove no send. Received stream text recovered
    from the context-bound spool remains partial, never a completed response.
    """

    def __init__(self, grant):
        if type(grant) is not HttpGrant:
            raise AccessBlocked("EXACT_HTTP_GRANT_REQUIRED")
        self.grant = grant
        self._attempts = set()
        self._lock = threading.Lock()
        self.frames = {}

    def _process(self, path, timeout, credential_environment):
        return BoundedCommandProcess(
            (sys.executable, "-m", "consilium.shell.api_process_worker", str(path)),
            timeout_seconds=timeout,
            credential_environment=credential_environment,
        )

    def send(self, wire, *, attempt_id, timeout_seconds):
        grant = self.grant
        grant.validate(wire)
        with self._lock:
            if (
                type(attempt_id) is not UUID
                or not attempt_id.int
                or attempt_id in self._attempts
                or type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds)
                or not 0 < timeout_seconds <= 900
            ):
                raise AccessBlocked("INVALID_OR_REPEATED_ATTEMPT")
            secret = credential_value(grant)
            raw = encode_process_request(grant, wire, attempt_id, timeout_seconds)
            # Reserve before spawning; any later failure may have followed a send.
            self._attempts.add(attempt_id)
        invalid = False
        try:
            with tempfile.TemporaryDirectory(prefix="consilium-api-") as directory:
                path = Path(directory) / "request.json"
                path.write_bytes(raw)
                path.chmod(0o600)
                process = self._process(
                    path, timeout_seconds, {grant.credential_env: secret}
                )
                try:
                    result = decode_process_outcome(
                        process.run(), grant, wire, attempt_id
                    )
                except Exception:  # noqa: BLE001 -- salvage only context-bound received bytes
                    result = HttpOutcome("UNKNOWN_DELIVERY", "TRANSPORT_INTERRUPTED")
                try:
                    frames = read_progress(
                        path.with_name("response.frames"), grant, wire, attempt_id
                    )
                except Exception:  # noqa: BLE001 -- absent/invalid spool proves nothing
                    frames = None
                if frames is not None:
                    self.frames[attempt_id] = frames
                    if result.code == "TRANSPORT_INTERRUPTED":
                        result = outcome_from_frames(wire, frames)
        except Exception:  # noqa: BLE001 -- do not log subprocess/request/credential details
            invalid = True
        if invalid:
            return HttpOutcome("UNKNOWN_DELIVERY", "TRANSPORT_INTERRUPTED")
        return result
