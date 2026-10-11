#!/usr/bin/env python3
"""Actual isolated Chromium layout tests on loopback, not a provider test."""

import contextlib
import http.server
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

import qualityctl as q

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from consilium.adapters.cdp_layout_reader import SCOPE, CdpLayoutReader
from consilium.adapters.cdp_process_reader import CdpProcessLayoutReader
from consilium.adapters.cdp_read_only import CdpReadOnlySession
from consilium.adapters.cdp_websocket import connect_read_only

HTML = b'''<!doctype html><html><head><style>
.gone{display:none}.invisible{visibility:hidden}.transparent{opacity:0}
</style></head><body><main id="answer">Visible answer
<span class="gone">display secret</span><span class="invisible">hidden secret</span>
<div class="transparent"><span>transparent secret</span></div>
<script type="application/json">script secret</script>
</main><aside>foreign secret</aside><div id="hidden" class="gone">hidden root secret</div>
</body></html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *_args):
        pass


class ChromiumLayoutProbe(unittest.TestCase):
    endpoint = target_id = url = ""

    def reader(self, selector="#answer", **changes):
        return CdpProcessLayoutReader(**{
            "endpoint": self.endpoint, "target_id": self.target_id,
            "expected_url": self.url, "selector": selector, "timeout_seconds": 10, **changes})

    def test_owned_process_reads_visible_layout_and_excludes_hidden_foreign_script_text(self):
        result = self.reader()()
        self.assertEqual(result.text.strip(), "Visible answer")
        self.assertEqual(result.scope, SCOPE)

    def test_direct_and_owned_reads_have_same_text_and_surface(self):
        with CdpReadOnlySession(self.endpoint, connect_read_only) as session:
            direct = CdpLayoutReader(session, target_id=self.target_id,
                                      expected_url=self.url, selector="#answer")()
        self.assertEqual(self.reader()(), direct)

    def test_hidden_selected_root_is_empty(self):
        self.assertEqual(self.reader(selector="#hidden")().text, "")

    def test_ambiguous_or_missing_subtrees_are_rejected(self):
        for selector in ("span", "#missing"):
            with self.assertRaisesRegex(ValueError, "CDP_PROCESS_READ_FAILED"):
                self.reader(selector=selector)()

    def test_changed_expected_url_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "CDP_PROCESS_READ_FAILED"):
            self.reader(expected_url=self.url + "different")()

    def test_script_and_navigation_commands_remain_forbidden(self):
        for method, params in [("Runtime.evaluate", {"expression": "document.body.remove()"}),
                               ("Page.navigate", {"url": self.url})]:
            with CdpReadOnlySession(self.endpoint, connect_read_only) as session:
                with self.assertRaisesRegex(ValueError, "CDP_READ_FAILED"):
                    session.read(method, **params)
                self.assertIsNone(session.socket)
        self.assertEqual(self.reader()().text.strip(), "Visible answer")


def probe(binary):
    with tempfile.TemporaryDirectory(prefix="consilium-layout-browser-") as folder:
        profile = Path(folder) / "profile"
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/fixture"
        command = [binary, "--no-sandbox", "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                   "--disable-background-networking", "--disable-sync", "--disable-extensions",
                   "--disable-component-update", "--remote-debugging-address=127.0.0.1",
                   "--remote-debugging-port=0", "--user-data-dir=" + str(profile),
                   "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", url]
        # This disposable loopback-only container fixture lacks a usable
        # Chromium OS sandbox. It is never an authenticated provider browser.
        browser = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=os.name != "nt")
        try:
            deadline = time.monotonic() + 15
            port_file = profile / "DevToolsActivePort"
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            target = None
            while time.monotonic() < deadline:
                if browser.poll() is not None:
                    raise RuntimeError("CHROMIUM_START_FAILED")
                if port_file.exists():
                    port = int(port_file.read_text().splitlines()[0])
                    with opener.open(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                        targets = json.load(response)
                    matching = [t for t in targets if t.get("type") == "page" and t.get("url") == url]
                    if len(matching) == 1:
                        target = matching[0]
                        break
                time.sleep(.05)
            if target is None:
                raise RuntimeError("CHROMIUM_TARGET_NOT_READY")
            ChromiumLayoutProbe.endpoint = target["webSocketDebuggerUrl"]
            ChromiumLayoutProbe.target_id = target["id"]
            ChromiumLayoutProbe.url = url
            return unittest.TextTestRunner(verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ChromiumLayoutProbe))
        finally:
            if os.name != "nt":
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(browser.pid, signal.SIGTERM)
            else:
                browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(browser.pid, signal.SIGKILL)
                else:
                    browser.kill()
                browser.wait(timeout=5)
            server.shutdown()
            server.server_close()
            thread.join(2)


def main():
    before = q.source_digest(ROOT)
    report = {"scope": "ACTUAL_CHROMIUM_LOCAL_LAYOUT_NOT_PROVIDER_ACCEPTANCE", "status": "NOT_RUN",
              "source_digest_before": before, "provider_calls": 0, "api_calls": 0,
              "browser_profile": "OWNED_DISPOSABLE_NO_LOGIN", "phase_accepted": False,
              "host": platform.system(), "tests": 0}
    binary = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if binary is None:
        report["reason"] = "CHROMIUM_UNAVAILABLE"
    else:
        try:
            report["browser_version"] = subprocess.check_output([binary, "--version"], text=True, timeout=5).strip()
            result = probe(binary)
            report.update(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          skipped=len(result.skipped), status="PASS" if result.wasSuccessful() else "FAIL")
        except Exception as exc:  # noqa: BLE001 -- private paths and protocol data
            report.update(status="FAIL", reason=type(exc).__name__)
    report["source_digest_after"] = q.source_digest(ROOT)
    if report["source_digest_after"] != before:
        report["status"] = "FAIL"
    folder = ROOT / "evidence/cdp-layout-browser-probe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "RUN.json").write_bytes(q.encoded(report))
    print(json.dumps(report))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
