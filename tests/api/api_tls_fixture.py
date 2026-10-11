"""Only a loopback TLS test endpoint with explicitly synthetic credentials."""

import os
import re
import sys
from pathlib import Path

from consilium.adapters.api_http import https_once
from consilium.adapters.api_process_progress import ProgressWriter
from consilium.adapters.api_process_wire import decode_process_request
from consilium.shell.api_process_worker import execute

config, endpoint = sys.argv[1:]
if not re.fullmatch(
    r"https://127\.0\.0\.1:[0-9]+/(success|partial|finished|quota)", endpoint
):
    raise SystemExit(2)
raw = Path(config).read_bytes()
grant, wire, attempt, _timeout = decode_process_request(raw)
if os.environ.get(grant.credential_env) != "synthetic-loopback-key":
    raise SystemExit(2)
writer = ProgressWriter(Path(config).with_name("response.frames"), grant, wire, attempt)


def exchange(_endpoint, headers, body, timeout):
    return https_once(endpoint, headers, body, timeout, on_progress=writer)


sys.stdout.buffer.write(execute(raw, http=exchange))
