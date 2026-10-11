"""Owned finite raw-DOM acquisition; never a Qwen completion observation."""

import json
import math
import sys
import tempfile
from pathlib import Path

from consilium.adapters.cdp_dom_wire import decode_dom_output
from consilium.adapters.cdp_read_only import CdpDomReader, CdpReadOnlySession
from consilium.shell.bounded_read_process import BoundedReadProcess


class CdpProcessDomReader:
    """Use only the packaged read-only command, with a private temporary config."""

    def __init__(self, *, endpoint, target_id, expected_url, selector, timeout_seconds=10):
        invalid = False
        try:
            if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                    or not 0 < timeout_seconds <= 60):
                raise ValueError("timeout")
            session = CdpReadOnlySession(endpoint, lambda *_: None, timeout=timeout_seconds)
            CdpDomReader(session, target_id=target_id, expected_url=expected_url, selector=selector)
            session.close()
        except Exception:  # noqa: BLE001 -- private configuration
            invalid = True
        if invalid:
            raise ValueError("CDP_PROCESS_CONFIGURATION_INVALID")
        self.config = {"endpoint": endpoint, "target_id": target_id, "expected_url": expected_url,
                       "selector": selector, "timeout_seconds": timeout_seconds}

    def __call__(self):
        invalid = False
        try:
            with tempfile.TemporaryDirectory(prefix="consilium-dom-") as directory:
                config = Path(directory) / "read.json"
                config.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")
                config.chmod(0o600)
                process = BoundedReadProcess((sys.executable, "-m", "consilium.shell.cdp_dom_read", str(config)),
                                             timeout_seconds=self.config["timeout_seconds"])
                observation = decode_dom_output(process.run(), selector=self.config["selector"])
                if (observation.target_id != self.config["target_id"]
                        or observation.url != self.config["expected_url"]):
                    raise ValueError("binding")
        except Exception:  # noqa: BLE001 -- process errors and DOM data remain private
            invalid = True
        if invalid:
            raise ValueError("CDP_PROCESS_READ_FAILED")
        return observation
