"""Finite execution without retry; command authorization belongs to callers."""

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def _stop_owned(worker, deadline):
    if os.name == "nt":
        if worker.poll() is None:
            worker.kill()  # Worker exit closes its sole job handle.
    else:
        try:
            os.killpg(worker.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    worker.wait(timeout=max(0.001, deadline - time.monotonic()))


class BoundedCommandProcess:
    """Execute one explicit command in an owned tree; no shell or retry.

    Caller authorizes every command effect; this is not a sandbox or dispatch gate.
    stdout is bounded, stderr discarded, cleanup has five additional seconds.
    The existing portable worker contains descendants, never an attached browser.
    """

    ERROR_PREFIX = "BOUNDED_COMMAND"
    MAX_SECONDS = 900

    def _code(self, suffix):
        return self.ERROR_PREFIX + "_" + suffix

    def __init__(self, command: tuple[str, ...], *, timeout_seconds=30.0, credential_environment=None):
        if (
            type(command) is not tuple or not command
            or any(type(arg) is not str or not arg or "\0" in arg for arg in command)
            or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= self.MAX_SECONDS
        ):
            raise ValueError(self._code("CONFIGURATION_INVALID"))
        if credential_environment is not None and (
            type(credential_environment) is not dict
            or any(key not in {"GEMINI_API_KEY", "DASHSCOPE_API_KEY"} or type(value) is not str or "\0" in value
                   for key, value in credential_environment.items())
        ):
            raise ValueError(self._code("CONFIGURATION_INVALID"))
        self._pin_credentials = credential_environment is not None
        self._credential_environment = dict(credential_environment or {})
        self.command = command
        self.timeout_seconds = float(timeout_seconds)

    def run(self, *, max_bytes=3 * 1048576):
        if type(max_bytes) is not int or not 0 < max_bytes <= 3 * 1048576:
            raise ValueError(self._code("CONFIGURATION_INVALID"))
        output = bytearray()
        overflow, stream_failed = threading.Event(), threading.Event()
        failure = None
        with tempfile.TemporaryDirectory(prefix="consilium-read-") as directory:
            config = Path(directory) / "command.json"
            config.write_text(json.dumps({"command": self.command, "parent_pid": os.getpid()}))
            start = time.monotonic()
            environment = dict(os.environ)
            package_root = str(Path(__file__).resolve().parents[2])
            environment["PYTHONPATH"] = package_root + (
                os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
            )
            if self._pin_credentials:
                for key in ("GEMINI_API_KEY", "DASHSCOPE_API_KEY"):
                    environment.pop(key, None)
            environment.update(self._credential_environment)
            try:
                worker = subprocess.Popen(
                    [sys.executable, "-m", "consilium.shell.qwen_reader_worker", str(config)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    shell=False, start_new_session=os.name != "nt",
                    env=environment,
                )
            except OSError:
                failure = self._code("START_FAILED")
            if failure:
                raise ValueError(failure)

            def drain():
                try:
                    while chunk := worker.stdout.read(65536):
                        if len(output) + len(chunk) > max_bytes:
                            overflow.set()
                            return
                        output.extend(chunk)
                except OSError:
                    stream_failed.set()

            thread = threading.Thread(target=drain, daemon=True)
            thread.start()
            try:
                while worker.poll() is None:
                    if overflow.is_set():
                        failure = self._code("OUTPUT_OVERSIZED")
                        break
                    remaining = self.timeout_seconds - (time.monotonic() - start)
                    if remaining <= 0:
                        failure = self._code("TIMEOUT")
                        break
                    try:
                        worker.wait(timeout=min(0.02, remaining))
                    except subprocess.TimeoutExpired:
                        pass
                if time.monotonic() - start >= self.timeout_seconds and failure is None:
                    failure = self._code("TIMEOUT")
                if failure is None and worker.returncode != 0:
                    failure = self._code("PROCESS_FAILED")
            finally:
                cleanup_deadline = time.monotonic() + 5
                try:
                    _stop_owned(worker, cleanup_deadline)
                except (OSError, subprocess.TimeoutExpired):
                    failure = self._code("CLEANUP_FAILED")
                thread.join(timeout=max(0, cleanup_deadline - time.monotonic()))
                if not thread.is_alive():
                    worker.stdout.close()
            if thread.is_alive() or stream_failed.is_set():
                failure = self._code("STREAM_FAILED")
            elif overflow.is_set():
                failure = self._code("OUTPUT_OVERSIZED")
        if failure:
            raise ValueError(failure)
        return bytes(output)


class BoundedReadProcess(BoundedCommandProcess):
    """Compatibility wrapper for authorized read-only observation commands."""

    ERROR_PREFIX = "BOUNDED_READER"
    MAX_SECONDS = 60
