"""One explicit HTTPS attempt; no live product admission and no retry."""

import sys
from pathlib import Path

from consilium.adapters.api_http import ApiHttpTransport, https_once
from consilium.adapters.api_process_progress import ProgressWriter
from consilium.adapters.api_process_wire import (
    MAX_PROCESS_BYTES,
    decode_process_request,
    encode_process_outcome,
)
from consilium.shell.qwen_saved_read import bounded_file


def execute(raw, *, http=https_once, progress_path=None):
    """Injected exchange is for tests; CLI always uses the packaged HTTPS code."""
    invalid = False
    try:
        grant, wire, attempt, timeout = decode_process_request(raw)
        exchange = http
        if progress_path is not None and http is https_once:
            writer = ProgressWriter(progress_path, grant, wire, attempt)

            def exchange(*args):
                return https_once(*args, on_progress=writer)

        result = ApiHttpTransport(grant, exchange).send(
            wire, attempt_id=attempt, timeout_seconds=timeout
        )
        output = encode_process_outcome(result, grant, wire, attempt)
    except Exception:  # noqa: BLE001 -- credential/request/response details never escape
        invalid = True
    if invalid:
        raise ValueError("API_PROCESS_EXECUTION_FAILED")
    return output


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("API_PROCESS_REQUIRES_PRIVATE_REQUEST", file=sys.stderr)
        return 2
    invalid = False
    try:
        output = execute(
            bounded_file(argv[0], MAX_PROCESS_BYTES),
            progress_path=Path(argv[0]).with_name("response.frames"),
        )
    except Exception:  # noqa: BLE001 -- only a fixed code may reach stderr
        invalid = True
    if invalid:
        print("API_PROCESS_EXECUTION_FAILED", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    # CLI error codes are an exact byte protocol on both native targets.
    sys.stderr.reconfigure(newline="\n")
    raise SystemExit(main())
