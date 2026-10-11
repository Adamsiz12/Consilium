"""Owned fake exchange: never contact a provider or inspect real credentials."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from consilium.adapters.api_http import HttpFrames
from consilium.adapters.api_process_progress import ProgressWriter
from consilium.adapters.api_process_wire import decode_process_request
from consilium.shell.api_process_worker import execute

mode, config, marker = sys.argv[1:]
raw = Path(config).read_bytes()
grant, wire, _attempt, _timeout = decode_process_request(raw)


def http(*_args):
    other_key = (
        "DASHSCOPE_API_KEY"
        if grant.credential_env == "GEMINI_API_KEY"
        else "GEMINI_API_KEY"
    )
    if other_key in os.environ:
        raise ValueError("unrelated credential inherited")
    if os.environ.get(grant.credential_env) != "synthetic-pinned-key":
        raise ValueError("credential fixture mismatch")
    with Path(marker).open("ab") as stream:
        stream.write(b"X")
    if mode in ("hang", "partial-hang", "finished-hang"):
        if mode != "hang":
            writer = ProgressWriter(
                Path(config).with_name("response.frames"), grant, wire, _attempt
            )
            writer(200, b"")
            body = {
                "responseId": "fixture-1",
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": "پاسخ جزئی"}]}}
                ],
            }
            if mode == "finished-hang":
                body["candidates"][0]["finishReason"] = "STOP"
            payload = json.dumps(body, ensure_ascii=False)
            writer(
                200,
                (("data: " + payload + "\n\n") if wire.streaming else payload).encode(),
            )
        heartbeat = marker + ".heartbeat"
        helper = Path(__file__).parents[1] / "browser_probe/qwen_reader_fixture.py"
        subprocess.Popen((sys.executable, str(helper), "child", heartbeat))
        while True:
            time.sleep(0.02)
    if mode == "quota":
        return HttpFrames(429, ())
    if wire.provider == "google":
        body = {
            "responseId": "fixture-1",
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "پاسخ"}]},
                    "finishReason": "STOP",
                }
            ],
        }
    else:
        body = {
            "id": "fixture-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "پاسخ"},
                    "finish_reason": "stop",
                }
            ],
        }
    return HttpFrames(200, (json.dumps(body, ensure_ascii=False).encode(),))


output = execute(raw, http=http)
if mode == "truncated":
    output = output[: len(output) // 2]
elif mode == "wrong-context":
    value = json.loads(output)
    value["request_sha256"] = "0" * 64
    output = json.dumps(value).encode()
sys.stdout.buffer.write(output)
