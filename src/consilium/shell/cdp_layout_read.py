"""Fixed private CLI for owned rendered-layout acquisition; no page scripts."""

import json
import sys

from consilium.adapters.cdp_layout_reader import CdpLayoutReader, encode_layout_output
from consilium.adapters.cdp_read_only import CdpReadOnlySession
from consilium.adapters.cdp_websocket import connect_read_only
from consilium.adapters.qwen_page_reader import _require_bounded_depth, _unique_object
from consilium.shell.qwen_saved_read import bounded_file


def _constant(_value):
    raise ValueError("nonfinite")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    failed = False
    try:
        if len(argv) != 1:
            raise ValueError("configuration")
        raw = bounded_file(argv[0], 16384)
        _require_bounded_depth(raw)
        config = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_constant)
        if type(config) is not dict or set(config) != {"endpoint", "target_id", "expected_url", "selector", "timeout_seconds"}:
            raise ValueError("configuration")
        with CdpReadOnlySession(config["endpoint"], connect_read_only, timeout=config["timeout_seconds"]) as session:
            observation = CdpLayoutReader(session, target_id=config["target_id"],
                                          expected_url=config["expected_url"], selector=config["selector"])()
            result = encode_layout_output(observation, selector=config["selector"])
    except Exception:  # noqa: BLE001 -- private browser input and output
        failed = True
    if failed:
        print("CDP_LAYOUT_READ_FAILED", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    sys.stderr.reconfigure(newline="\n")
    raise SystemExit(main())
