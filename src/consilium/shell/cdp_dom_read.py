"""Private configuration CLI used by the owned DOM reader, with no retries."""

import json
import sys

from consilium.adapters.cdp_dom_wire import encode_dom_output
from consilium.adapters.cdp_read_only import CdpDomReader, CdpReadOnlySession
from consilium.adapters.cdp_websocket import connect_read_only
from consilium.adapters.qwen_page_reader import _require_bounded_depth, _unique_object
from consilium.shell.qwen_saved_read import bounded_file


def _constant(_value):
    raise ValueError("nonfinite")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("CDP_DOM_READ_REQUIRES_CONFIG", file=sys.stderr)
        return 2
    invalid = False
    try:
        raw = bounded_file(argv[0], 16384)
        _require_bounded_depth(raw)
        config = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_constant)
        json.dumps(config, allow_nan=False)
        if type(config) is not dict or set(config) != {"endpoint", "target_id", "expected_url", "selector", "timeout_seconds"}:
            raise ValueError("fields")
        with CdpReadOnlySession(config["endpoint"], connect_read_only, timeout=config["timeout_seconds"]) as session:
            observation = CdpDomReader(session, target_id=config["target_id"],
                                       expected_url=config["expected_url"], selector=config["selector"])()
            result = encode_dom_output(observation, selector=config["selector"])
    except Exception:  # noqa: BLE001 -- private input and page details must not escape
        invalid = True
    if invalid:
        print("CDP_DOM_READ_FAILED", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    # Preserve the fixed error-code framing when Windows translates newlines.
    sys.stderr.reconfigure(newline="\n")
    raise SystemExit(main())
