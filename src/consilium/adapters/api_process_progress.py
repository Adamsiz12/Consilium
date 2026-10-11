"""Private bounded response spool; recovery never authorizes a new dispatch."""

import base64
import json
import os

from consilium.adapters.api_http import MAX_BYTES, HttpFrames
from consilium.adapters.api_process_wire import (
    MAX_PROCESS_BYTES,
    _json,
    grant_hash,
    wire_hash,
)
from consilium.shell.qwen_saved_read import bounded_file


class ProgressWriter:
    def __init__(self, path, grant, wire, attempt):
        self.path = path
        self.identity = [grant_hash(grant), wire_hash(wire), str(attempt)]
        self.size = 0
        self.started = False
        self.file_size = 0
        self.status = None

    def __call__(self, status, chunk):
        if (
            type(status) is not int
            or not 100 <= status <= 599
            or type(chunk) is not bytes
        ):
            raise ValueError("API_PROGRESS_INVALID")
        if self.started and status != self.status:
            raise ValueError("API_PROGRESS_INVALID")
        if self.started and not chunk:
            return
        self.size += len(chunk)
        if self.size > MAX_BYTES:
            raise ValueError("API_PROGRESS_INVALID")
        record = (
            [1, *self.identity, status]
            if not self.started
            else base64.b64encode(chunk).decode("ascii")
        )
        encoded = json.dumps(record, separators=(",", ":")).encode() + b"\n"
        if self.file_size + len(encoded) > MAX_PROCESS_BYTES:
            raise ValueError("API_PROGRESS_INVALID")
        with self.path.open("ab" if self.started else "xb") as stream:
            if not self.started:
                self.path.chmod(0o600)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        self.file_size += len(encoded)
        self.status = status
        first = not self.started
        self.started = True
        if first and chunk:
            self.size -= len(chunk)
            self(status, chunk)


def _read_progress(path, grant, wire, attempt):
    raw = bounded_file(str(path), MAX_PROCESS_BYTES)
    lines = raw.split(b"\n")[:-1]  # An unfinished last write is not a received frame.
    if not lines:
        raise ValueError("API_PROGRESS_INVALID")
    header = _json(lines[0])
    if (
        type(header) is not list
        or len(header) != 5
        or type(header[0]) is not int
        or header[:4] != [1, grant_hash(grant), wire_hash(wire), str(attempt)]
        or type(header[4]) is not int
        or not 100 <= header[4] <= 599
    ):
        raise ValueError("API_PROGRESS_INVALID")
    chunks = []
    size = 0
    for line in lines[1:]:
        value = _json(line)
        if type(value) is not str:
            raise ValueError("API_PROGRESS_INVALID")
        chunk = base64.b64decode(value, validate=True)
        if base64.b64encode(chunk).decode("ascii") != value:
            raise ValueError("API_PROGRESS_INVALID")
        size += len(chunk)
        if size > MAX_BYTES:
            raise ValueError("API_PROGRESS_INVALID")
        chunks.append(chunk)
    return HttpFrames(header[4], tuple(chunks), True)


def read_progress(path, grant, wire, attempt):
    invalid = False
    try:
        frames = _read_progress(path, grant, wire, attempt)
    except Exception:  # noqa: BLE001 -- private file/body details never escape
        invalid = True
    if invalid:
        raise ValueError("API_PROGRESS_INVALID")
    return frames
