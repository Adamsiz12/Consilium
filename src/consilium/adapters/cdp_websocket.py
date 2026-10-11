"""Optional pinned WebSocket transport for explicit loopback page endpoints.

Install consilium-local[browser-read]. Run acquisition in an owned bounded
worker: the protocol receive deadline alone cannot interrupt a blocked send.
No proxy, compression, cookie headers, auto-ping or browser discovery is used.
"""

import math
from importlib.metadata import version

from consilium.adapters.cdp_read_only import MAX_MESSAGE_BYTES, _endpoint


def connect_read_only(endpoint, timeout):
    failed = False
    try:
        if (not _endpoint(endpoint) or type(timeout) not in (int, float)
                or not math.isfinite(timeout) or not 0 < timeout <= 60
                or version("websockets") != "16.0"):
            raise ValueError("configuration")
        from websockets.sync.client import connect
        socket = connect(endpoint, proxy=None, compression=None, open_timeout=timeout,
                         close_timeout=min(timeout, 1.0), max_size=MAX_MESSAGE_BYTES,
                         max_queue=1, ping_interval=None, user_agent_header=None)
    except Exception:  # noqa: BLE001 -- optional dependency and endpoint details are private
        failed = True
    if failed:
        raise ValueError("CDP_TRANSPORT_UNAVAILABLE")
    return socket
